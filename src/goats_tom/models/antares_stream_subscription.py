"""Module for `AntaresStreamSubscription` model."""

__all__ = ["AntaresStreamSubscription"]

from django.db import models


class AntaresStreamSubscription(models.Model):
    """Tracks the currently-configured ANTARES Kafka stream subscription.

    Only one row is expected to be meaningfully "current" at a time -- the
    most recently updated one. Submitting a new topic list creates/updates
    this row and (once wired up) restarts the `ingest_antares_stream`
    consumer with the new topics.

    Attributes
    ----------
    topics : `models.JSONField`
        List of Kafka topic names to subscribe to, e.g.
        ``["extragalactic_staging", "nuclear_transient_staging"]``.
    save_all_targets : `models.BooleanField`
        Whether all ingested loci should be saved as GOATS targets.
        Currently a no-op placeholder; not yet wired to any behavior.
    trigger_gemini_observations : `models.BooleanField`
        Whether ingested loci should automatically trigger Gemini
        observations. Currently a no-op placeholder; not yet wired to any
        behavior.
    handler_code : `models.TextField`
        Optional user-defined ``def myfilter(locus): ...`` function run
        against each locus before it's saved, acting as an additional
        filter on top of the topic subscription. See
        `goats_tom.antares_locus_handler` for the execution model and its
        restrictions.
    dramatiq_message_id : `models.CharField`
        Message ID of the currently-running `ingest_antares_stream`
        actor invocation, if any. Used to abort the running consumer
        before starting a new one with updated topics.
    is_running : `models.BooleanField`
        Whether a consumer is believed to currently be running for this
        subscription.
    updated_at : `models.DateTimeField`
        When this subscription was last changed.

    """

    topics = models.JSONField(default=list)
    save_all_targets = models.BooleanField(default=False)
    trigger_gemini_observations = models.BooleanField(default=False)
    handler_code = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Optional user-defined function named 'myfilter(locus)' run "
            "against each locus before it's saved. Return True to keep "
            "the locus, False to skip it. See "
            "goats_tom.antares_locus_handler for the execution model and "
            "its restrictions."
        ),
    )
    dramatiq_message_id = models.CharField(max_length=64, null=True, blank=True)
    is_running = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ANTARES stream subscription"
        verbose_name_plural = "ANTARES stream subscriptions"

    def __str__(self) -> str:
        return f"ANTARES topics: {', '.join(self.topics)}" if self.topics else "ANTARES topics: (none)"
