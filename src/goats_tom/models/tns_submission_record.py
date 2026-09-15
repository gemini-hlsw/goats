"""Module for `TNSSubmissionRecord` model."""

__all__ = ["TNSSubmissionRecord"]

from django.conf import settings
from django.db import models


class TNSSubmissionRecord(models.Model):
    """One attempt to post to TNS, and whose credentials it went out under.

    Sharing a bot means TNS attributes a post to the owner, who is
    accountable for it, while somebody else wrote it. Without a record the
    owner has no way to answer "who sent that?" -- TNS itself only knows
    the bot. That is the whole reason this table exists, so it records
    failed attempts too: an owner needs to see that somebody tried, not
    just that something succeeded.

    Names are stored as text alongside the foreign keys, on purpose. The
    keys are for joining and filtering; the text is what survives. A group
    can be renamed, credentials deleted, an account removed -- and the
    question the log answers ("what went out under my bot's name, and when")
    still has to be answerable afterwards. A row whose every field went
    `NULL` would be worse than no row.

    Attributes
    ----------
    submitted_by : `models.ForeignKey`
        Who filled in and sent the form. `SET_NULL`, since deleting a user
        must not erase the history of posts made under somebody else's
        bot -- `username` below is what keeps the row readable.
    display_name : `models.CharField`
        Snapshot of `submitted_by`'s full name at submission time, and what
        the log actually shows. Blank when they had set no full name, which
        renders as a dash rather than falling back to the username.
    username : `models.CharField`
        Snapshot of the username, kept but no longer displayed. A username
        is half of a login credential, so it does not belong on a page; it
        stays stored because it is the only identifier that still resolves
        to a specific account once `submitted_by` has been deleted, which
        is exactly when an owner most needs to answer "who sent that?".
    owner : `models.ForeignKey`
        Whose credentials were used. `SET_NULL` for the same reason.
    tns_group : `models.ForeignKey`
        The group posted through, if any. `SET_NULL`: a deleted group must
        not take the audit trail with it.
    group_name : `models.CharField`
        Snapshot of the group name. Blank when posting with no group.
    bot_id : `models.CharField`
        Snapshot of the bot ID, which is what TNS's own records will show.
    target_pk : `models.PositiveIntegerField`
        Primary key of the GOATS target, stored as a plain integer rather
        than a foreign key. `tom_targets.Target` is not a model at all --
        it is a module-level alias assigned at import time from
        ``settings.TARGET_MODEL_CLASS``, defaulting to `BaseTarget` -- so
        there is no ``tom_targets.target`` for Django's app registry to
        resolve, and a foreign key to it fails the system check outright.

        Pointing the key at `BaseTarget` instead would resolve, but would
        then be wrong for any deployment that sets
        ``TARGET_MODEL_CLASS`` to its own subclass, and `BaseTarget` is
        not declared ``swappable``, so Django offers no supported way to
        follow that setting from a foreign key.

        A plain integer also matches what
        `goats_tom.models.AntaresTargetSave` already does, and for the
        same reason it gives here: the audit trail must outlive the thing
        it points at. `object_name` below is the identifier that stays
        meaningful once a target is gone.
    object_name : `models.CharField`
        The object as named in the submission. The durable identifier --
        this, not `target_pk`, is what answers "what was reported".
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
        Resolves through `tom_targets.models.Target`, the runtime alias, so
        a deployment with its own ``TARGET_MODEL_CLASS`` gets its own model
        back. That is the reason the column is a plain integer rather than
        a foreign key; doing the lookup here keeps the awkwardness in one
        place instead of at every call site.

        Imported inside the method rather than at module scope: this module
        is loaded while the app registry is still populating, and importing
        `tom_targets.models` there would be a circular import.
        """
        if self.target_pk is None:
            return None
        from tom_targets.models import Target  # noqa: PLC0415

        return Target.objects.filter(pk=self.target_pk).first()
