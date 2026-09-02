"""Module for `DataLabJob` model."""

__all__ = ["DataLabJob"]

from django.db import models


class DataLabJob(models.Model):
    """One GOA download or DRAGONS reduction executed on Astro Data Lab.

    Notes
    -----
    **Deliberately not `RemoteJob`.** That table serves the ANTARES stream
    and is in use and correct. Generalizing it was tried and reverted: it
    changed a working system for features that did not exist yet, and added
    `kind` filters to the ANTARES supervisor guarding against rows nothing
    created. See *Keep ANTARES out of Phases 3 and 4* in ``STATUS.md``.

    The genuinely shared piece is `DataLabHeadlessClient`, which both use
    unchanged -- `launch`, `job_status`, `fetch_log` and `tail_ndjson` are
    already kind-neutral. Sharing a client is cheap; sharing a table would
    have meant every ANTARES query carrying a filter for rows it never wants.

    The cost is a second poll-and-reap implementation, which can drift from
    the ANTARES one. That is accepted: this is new code beside old code, not
    one behaviour written twice, and merging later with both callers known is
    easier than generalizing ahead of the second.

    **State here is a report, not a source of truth.** A detached runner
    cannot be inspected. `status` records what the runner last wrote to its
    own status file, so a job that dies abruptly leaves `RUNNING` behind
    forever. The supervisor must treat a stale `last_heartbeat` as
    authoritative over `status` -- the same rule `RemoteJob` documents, for
    the same reason.

    Attributes
    ----------
    kind : `models.CharField`
        Whether this job downloads or reduces. Decides which collector reads
        it, and the two report entirely different things.
    observation_record : `models.ForeignKey`
        What is being downloaded. Set for downloads, null for reductions.
    dragons_run : `models.ForeignKey`
        What is being reduced. Set for reductions, null for downloads.
    user : `models.ForeignKey`
        Who the job runs as, and whose VOSpace it writes to. Stored rather
        than derived through the observation record, because that record's
        owner could change between launch and collection while the files
        this job wrote stay where they were put.
    datalab_username : `models.CharField`
        The Data Lab account, which is **not** assumed to equal the GOATS
        username -- `VOSpaceStorage` resolves it the same way, and the two
        must agree or files are written under one name and looked for under
        another.
    job_id : `models.CharField`
        GOATS-assigned identifier, and the name of the remote job directory.
    remote_pid : `models.PositiveIntegerField`
        PID of the detached runner. Best-effort: there is no process API once
        detached, and a culled notebook server makes it unreachable.
    status, last_heartbeat : see the class note above.
    files_seen, files_kept : `models.PositiveIntegerField`
        What the runner reported. For a download, files found in the tarball
        and files successfully written to VOSpace; for a reduction, inputs
        and outputs.
    log_offset : `models.PositiveIntegerField`
        How many NDJSON log records the VM has already consumed, so polling
        resumes rather than restarting. See `tail_ndjson`.
    """

    class Kind(models.TextChoices):
        """What work a job is doing."""

        DOWNLOAD = "download", "GOA download"
        REDUCTION = "reduction", "DRAGONS reduction"

    class Status(models.TextChoices):
        """Lifecycle of a job."""

        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"
        FAILED = "failed", "Failed"
        # Distinct from FAILED: the runner never reported anything and its
        # heartbeat went stale, so what went wrong is unknown. Worth telling
        # apart, because FAILED carries a reason and this does not.
        LOST = "lost", "Lost"

    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)

    observation_record = models.ForeignKey(
        "tom_observations.ObservationRecord",
        on_delete=models.CASCADE,
        related_name="datalab_jobs",
        null=True,
        blank=True,
    )
    dragons_run = models.ForeignKey(
        "goats_tom.DRAGONSRun",
        on_delete=models.CASCADE,
        related_name="datalab_jobs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="datalab_jobs",
    )

    datalab_username = models.CharField(max_length=128)
    job_id = models.CharField(max_length=64, unique=True)
    session_id = models.CharField(max_length=64, null=True, blank=True)
    kernel_id = models.CharField(max_length=64, null=True, blank=True)
    remote_pid = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    files_seen = models.PositiveIntegerField(default=0)
    files_kept = models.PositiveIntegerField(default=0)
    log_offset = models.PositiveIntegerField(default=0)
    error = models.TextField(null=True, blank=True)

    remote_dir_deleted = models.BooleanField(default=False)
    launched_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Data Lab job"
        verbose_name_plural = "Data Lab jobs"
        indexes = [
            # The supervisor's hot query: everything still in flight, oldest
            # heartbeat first, so stale jobs are found without scanning
            # completed history.
            models.Index(
                fields=["status", "last_heartbeat"],
                name="datalabjob_status_heartbeat",
            ),
        ]
        ordering = ["-launched_at"]

    def __str__(self) -> str:
        return f"{self.job_id} ({self.kind}, {self.status})"

    @property
    def is_active(self) -> bool:
        """Whether this job may still be doing work."""
        return self.status in (self.Status.PENDING, self.Status.RUNNING)

    @property
    def owner(self):
        """Return the object this job was launched for."""
        if self.kind == self.Kind.DOWNLOAD:
            return self.observation_record
        return self.dragons_run

    def is_stale(self, after_seconds: float) -> bool:
        """Whether this job has gone quiet for longer than `after_seconds`.

        Parameters
        ----------
        after_seconds : float
            Silence tolerated before a job is presumed dead.

        Returns
        -------
        bool

        Notes
        -----
        Measured from `last_heartbeat`, falling back to `launched_at` when
        the runner has never reported -- a job that fails before writing its
        first status file would otherwise never look stale and would sit
        `PENDING` forever.
        """
        from django.utils import timezone  # noqa: PLC0415

        if not self.is_active:
            return False
        reference = self.last_heartbeat or self.launched_at
        if reference is None:
            return False
        return (timezone.now() - reference).total_seconds() > after_seconds

    def clean(self) -> None:
        """Check the link matching `kind` is set.

        Raises
        ------
        `django.core.exceptions.ValidationError`
            If the wrong link is populated for this kind.

        Notes
        -----
        Not a database constraint: one would need rewriting for every new
        kind, and the `IntegrityError` it raises from inside a save says far
        less than a field-level message. The supervisor is the real consumer
        -- a job with no owner is one it cannot collect from, and it should
        find out here rather than at a `None` three calls later.
        """
        from django.core.exceptions import ValidationError  # noqa: PLC0415

        expected = (
            "observation_record"
            if self.kind == self.Kind.DOWNLOAD
            else "dragons_run"
        )
        if getattr(self, f"{expected}_id", None) is None:
            raise ValidationError(
                {expected: f"A {self.get_kind_display()} job must set {expected}."}
            )
