"""Module for `GeminiTriggerRecord` model."""

__all__ = ["GeminiTriggerRecord"]

from django.db import models


class GeminiTriggerRecord(models.Model):
    """One automatic Gemini trigger attempt for one locus.

    A row is created *before* GPP is contacted, not after, and is unique on
    ``(subscription, locus_id)``. That makes it an idempotency key rather than
    just an audit log: a second attempt for the same locus cannot insert, so
    it stops before touching GPP.

    This matters because the dangerous failure is not a refused trigger but a
    duplicated one. If a clone succeeds in GPP and the response is lost on the
    way back, a naive retry would create a second observation on the same
    target and charge the allocation twice. Reserving the row first means even
    a mistaken retry is harmless.

    For the same reason `STATUS_FAILED` is terminal and never retried
    automatically. A failure after the clone began is ambiguous -- the
    observation may exist in GPP despite the error -- so it is surfaced for a
    human to check in Explore rather than guessed at. ANTARES re-alerts an
    active locus repeatedly, so an automatic retry would otherwise fire again
    within minutes.

    Attributes
    ----------
    subscription : `models.ForeignKey`
        The subscription that triggered. `CASCADE`: these records describe its
        activity and have no meaning without it.
    locus_id : `models.CharField`
        The ANTARES locus that prompted the trigger.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_SUCCESS`, `STATUS_FAILED`,
        `STATUS_SKIPPED`.
    gpp_observation_id : `models.CharField`
        The observation created in GPP, when one was. Blank otherwise.
    gpp_target_id : `models.CharField`
        The target created in GPP, when one was. Recorded separately because a
        run can fail between creating the target and cloning the observation,
        leaving an orphaned target somebody has to clean up -- and the id is
        the only way to find it.
    execution_time_hours : `models.FloatField`
        What this observation was expected to cost, as reported by GPP at
        trigger time. Kept so the running total can be shown without
        re-querying, and so it is still known if the observation is later
        deleted.
    detail : `models.TextField`
        Why it was skipped, or what went wrong. The user-facing explanation.
    created_at : `models.DateTimeField`
        When the attempt started.
    updated_at : `models.DateTimeField`
        When it last changed state.

    """

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    subscription = models.ForeignKey(
        "goats_tom.AntaresStreamSubscription",
        on_delete=models.CASCADE,
        related_name="gemini_triggers",
    )
    locus_id = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    gpp_observation_id = models.CharField(max_length=128, blank=True, default="")
    gpp_target_id = models.CharField(max_length=128, blank=True, default="")
    execution_time_hours = models.FloatField(null=True, blank=True)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gemini trigger record"
        verbose_name_plural = "Gemini trigger records"
        ordering = ["-created_at"]
        constraints = [
            # The idempotency key. See the class docstring: this is what makes
            # a duplicated trigger impossible rather than merely unlikely.
            models.UniqueConstraint(
                fields=["subscription", "locus_id"],
                name="unique_gemini_trigger_per_locus",
            )
        ]

    def __str__(self) -> str:
        return f"{self.locus_id} -> {self.status}"

    @property
    def counts_towards_cap(self) -> bool:
        """Whether this attempt consumes one of the subscription's triggers.

        Returns
        -------
        bool
            `True` unless the attempt was skipped.

        Notes
        -----
        A skipped attempt never reached GPP, so counting it would let a
        refusal consume the very budget it was protecting -- and once the cap
        was reached, every further skip would keep it there.

        Failures *do* count. A failure after the clone began may have created
        an observation despite the error, so treating it as free risks
        spending the allocation twice over.
        """
        return self.status != self.STATUS_SKIPPED
