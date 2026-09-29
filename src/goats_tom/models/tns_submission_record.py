"""Module for `TNSSubmissionRecord` model."""

__all__ = ["TNSSubmissionRecord"]

from django.conf import settings
from django.db import models


class TNSSubmissionRecord(models.Model):
    """One attempt to post to TNS, and whose credentials it went out under.

    Sharing a bot means TNS attributes the post to the owner, who is
    accountable for it, while somebody else wrote it. Failed attempts are
    recorded too -- an owner needs to see that somebody tried. Names are
    snapshot as text beside the foreign keys so the log stays readable
    after a group, account or credential is deleted.

    Attributes
    ----------
    submitted_by : `models.ForeignKey`
        Who filled in and sent the form.
    display_name : `models.CharField`
        Snapshot of their full name, and what the log shows.
    username : `models.CharField`
        Snapshot of the username. Stored but not displayed, being half of a
        login credential; it is the only identifier that still resolves to
        an account once `submitted_by` is gone.
    owner : `models.ForeignKey`
        Whose credentials were used.
    tns_group : `models.ForeignKey`
        The group posted through, if any.
    group_name : `models.CharField`
        Snapshot of the group name. Blank when posting with no group.
    bot_id : `models.CharField`
        Snapshot of the bot ID, which is what TNS's own records show.
    target_pk : `models.PositiveIntegerField`
        Primary key of the GOATS target, as a plain integer. A foreign key
        is impossible: `tom_targets.Target` is a module-level alias
        assigned from ``settings.TARGET_MODEL_CLASS``, so there is no model
        for the app registry to resolve.
    object_name : `models.CharField`
        The object as named in the submission, and the identifier that
        stays meaningful once a target is gone.
    kind : `models.CharField`
        `KIND_REPORT` or `KIND_CLASSIFY`.
    succeeded : `models.BooleanField`
        Whether TNS accepted it.
    iau_name : `models.CharField`
        The name TNS returned, when it returned one.
    error : `models.TextField`
        What went wrong, for failures.
    created_at : `models.DateTimeField`
        When the attempt was made.
    """

    KIND_REPORT = "report"
    KIND_CLASSIFY = "classify"
    KIND_CHOICES = [
        (KIND_REPORT, "Discovery report"),
        (KIND_CLASSIFY, "Classification"),
    ]

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tns_submissions",
    )
    display_name = models.CharField(max_length=300, blank=True, default="")
    username = models.CharField(max_length=150, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tns_submissions_via_my_bot",
    )
    tns_group = models.ForeignKey(
        "goats_tom.TNSGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    group_name = models.CharField(max_length=100, blank=True, default="")
    bot_id = models.CharField(max_length=50, blank=True, default="")
    target_pk = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    object_name = models.CharField(max_length=200, blank=True, default="")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    succeeded = models.BooleanField(default=False)
    iau_name = models.CharField(max_length=100, blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "TNS submission record"
        verbose_name_plural = "TNS submission records"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        outcome = "ok" if self.succeeded else "failed"
        return (
            f"{self.display_name or self.username or 'unknown'} {self.kind} "
            f"{self.object_name} via {self.group_name or 'no group'} "
            f"({outcome})"
        )

    @property
    def target(self):
        """The GOATS target, if it still exists.

        Returns
        -------
        `tom_targets.models.Target` or None
            `None` once the target has been deleted, which is expected --
            the record outlives it deliberately.

        Notes
        -----
        Resolves through the runtime alias, so a deployment with its own
        ``TARGET_MODEL_CLASS`` gets its own model back. Imported inside the
        method because this module loads while the app registry is still
        populating.
        """
        if self.target_pk is None:
            return None
        from tom_targets.models import Target  # noqa: PLC0415

        return Target.objects.filter(pk=self.target_pk).first()
