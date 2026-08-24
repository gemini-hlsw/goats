"""Module for `RemoteJob` model."""

__all__ = ["RemoteJob"]

from django.db import models


class RemoteJob(models.Model):
    """One window of stream consumption executed on Astro Data Lab.

    Created when `goats_tom.executors.DataLabExecutor` launches a runner and
    updated as the supervisor polls it. A subscription in `datalab` mode has
    many of these over its lifetime -- one per ~10 minute window, or one
    long-lived row in continuous mode.

    Kept in a separate table rather than as columns on
    `AntaresStreamSubscription` for two reasons. The subscription is
    one-per-user and describes intent that outlives any particular run,
    whereas these rows are per-execution and disposable; and every field here
    is meaningless in `local` mode, so folding them in would put remote-only
    state on the desktop install's hot path. That also keeps the migration
    purely additive -- one new table, no changes to existing ones.

    **State here is a report, not a source of truth.** A detached runner
    cannot be inspected: `status` records what the runner last wrote to its
    own status file, so a job that dies abruptly leaves `RUNNING` behind
    forever. The supervisor must treat a stale `last_heartbeat` as
    authoritative over `status`. Correctness comes from `generation` fencing,
    never from believing this row.

    Attributes
    ----------
    subscription : `models.ForeignKey`
        The subscription this window served. `CASCADE`: job history is
        meaningless once the subscription is gone, and these rows carry no
        science data -- loci live in `AntaresLocus`.
    generation : `models.PositiveIntegerField`
        Fencing token this run was launched under, copied from the
        subscription at launch. Rows arriving from a run whose generation has
        since advanced are discarded at ingest rather than trusted, which is
        what makes stopping a remote process merely an optimisation.
    run_number : `models.PositiveIntegerField`
        The subscription's run this window belongs to, for grouping windows
        in the dashboard.
    datalab_username : `models.CharField`
        The Data Lab account the job ran as. Stored rather than derived,
        because it is what the supervisor authenticates as when draining the
        MyDB table, and a PI could change their linked credentials between
        launch and drain.
    job_id : `models.CharField`
        GOATS-assigned identifier; also the name of the remote job directory.
        Unique because it addresses a specific directory on a specific
        account.
    session_id, kernel_id : `models.CharField`
        Jupyter session and kernel that ran the launcher cell. Expected to be
        dead almost immediately -- the kernel is released once the runner
        detaches -- and retained only for support and log correlation.
    remote_pid : `models.PositiveIntegerField`
        PID of the detached runner on Data Lab. `null` if the launcher cell
        reported none, which is itself a failure signal. Best-effort only:
        there is no process API once detached, and if the notebook server has
        been culled the PID is unreachable.
    status : `models.CharField`
        Last state the runner reported. See the class note above.
    last_heartbeat : `models.DateTimeField`
        When the supervisor last saw the runner's status file advance. The
        real liveness signal, since `status` cannot report a crash.
    restart_count : `models.PositiveIntegerField`
        How many times a continuous job has been relaunched after going
        stale. Drives backoff, and a persistently climbing count means the
        handler or the account is the problem, not the launch.
    loci_seen, loci_kept : `models.PositiveIntegerField`
        Counts the runner reported for this window. `seen` far exceeding
        `kept` is normal; `kept` approaching `seen` on a busy topic suggests
        a handler that filters nothing, which is what the ingest rate cap
        exists for.
    error : `models.TextField`
        Reason and traceback when the runner failed, so a PI can see why
        their handler aborted without an administrator reading remote logs.
    launched_at, finished_at : `models.DateTimeField`
        Window boundaries as observed by the VM.
    """

    class Status(models.TextChoices):
        """Lifecycle of a remote window."""

        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"
        FAILED = "failed", "Failed"
        # Distinct from FAILED: the runner never reported anything and its
        # heartbeat went stale, so what went wrong is unknown. Worth telling
        # apart, because FAILED carries a reason and this does not.
        LOST = "lost", "Lost"

    subscription = models.ForeignKey(
        "goats_tom.AntaresStreamSubscription",
        on_delete=models.CASCADE,
        related_name="remote_jobs",
    )
    generation = models.PositiveIntegerField(default=0)
    run_number = models.PositiveIntegerField(default=0, db_index=True)

    datalab_username = models.CharField(max_length=128)
    job_id = models.CharField(max_length=64, unique=True)
    session_id = models.CharField(max_length=64, null=True, blank=True)
    kernel_id = models.CharField(max_length=64, null=True, blank=True)
    remote_pid = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    restart_count = models.PositiveIntegerField(default=0)

    loci_seen = models.PositiveIntegerField(default=0)
    loci_kept = models.PositiveIntegerField(default=0)
    error = models.TextField(null=True, blank=True)

    launched_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "remote job"
        verbose_name_plural = "remote jobs"
        indexes = [
            # The supervisor's hot query: every job still in flight, oldest
            # heartbeat first, so stale ones are found without scanning
            # completed history.
            models.Index(
                fields=["status", "last_heartbeat"],
                name="remotejob_status_heartbeat",
            ),
            models.Index(
                fields=["subscription", "-launched_at"],
                name="remotejob_sub_launched",
            ),
        ]
        ordering = ["-launched_at"]

    def __str__(self) -> str:
        return f"{self.job_id} ({self.status})"

    @property
    def is_active(self) -> bool:
        """Whether this job may still be doing work."""
        return self.status in (self.Status.PENDING, self.Status.RUNNING)

    def is_stale(self, timeout_seconds: float) -> bool:
        """Whether an active job has stopped reporting.

        Parameters
        ----------
        timeout_seconds : float
            How long without a heartbeat counts as stale. Should exceed the
            runner's own deadline, so a job that is merely finishing is not
            mistaken for a dead one.

        Returns
        -------
        bool
            `True` if the job is active but its heartbeat has aged out.

        Notes
        -----
        A job that has never reported is judged from `launched_at`: a runner
        that dies before writing its first status would otherwise look
        permanently fresh and never be reaped.
        """
        from django.utils import timezone  # noqa: PLC0415

        if not self.is_active:
            return False
        reference = self.last_heartbeat or self.launched_at
        if reference is None:
            return False
        return (timezone.now() - reference).total_seconds() > timeout_seconds
