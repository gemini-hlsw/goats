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
    group : `models.CharField`
        Optional Kafka consumer group name. If blank, a built-in default
        is used (see `goats_tom.tasks.ingest_antares_stream.DEFAULT_GROUP`).
        Set here rather than alongside the API credentials, since it's
        changed far more often than the credentials themselves (e.g. to
        force a full replay from a fresh group with no committed offset).
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
        restrictions. Validated with a real dry run at submission time;
        if it still fails against a real locus from the stream, the
        consumer stops entirely (fail-closed) rather than skipping that
        locus and continuing.
    dramatiq_message_id : `models.CharField`
        Message ID of the currently-running `ingest_antares_stream`
        actor invocation, if any. Used to abort the running consumer
        before starting a new one with updated topics.
    is_running : `models.BooleanField`
        Whether a consumer is believed to currently be running for this
        subscription. Set to `False` both by deliberate stop/restart
        actions and by the consumer itself if `handler_code` fails.
    last_handler_warning : `models.TextField`
        The error from `handler_code` that stopped the consumer, if any,
        including the handler source itself. Shown on the ingestion page
        so a broken filter is visible without checking server logs.
        Cleared the next time a (new) consumer is successfully started.
    last_handler_warning_at : `models.DateTimeField`
        When `last_handler_warning` was last set.
    generation : `models.PositiveIntegerField`
        Incremented every time a new consumer is started (restart or
        stop). Passed into `ingest_antares_stream` as the generation it
        was started with; the actor checks, before every write, that its
        generation still matches the subscription's *current* generation
        in the database, and stops immediately if not. This is a fencing
        token: it guarantees an old, not-yet-fully-stopped consumer can
        never write data after a newer one has started, closing the
        window that a fixed delay after `abort()` could only shrink, not
        eliminate (`dramatiq_abort` can't interrupt a blocking C-level
        Kafka call, and provides no way to confirm a specific message has
        actually stopped).
    updated_at : `models.DateTimeField`
        When this subscription was last changed.
    draft_topics : `models.TextField`
        The raw (unparsed, possibly malformed) topics text from the most
        recent form submission that FAILED validation, if any. Separate
        from `topics` (which only reflects the last successfully-started
        consumer) so a failed attempt's typed values survive navigating
        away and back, until either a successful submission (which clears
        all draft_* fields) or the user explicitly starts over.
    draft_group : `models.CharField`
        Same idea as `draft_topics`, for the group field.
    draft_save_all_targets : `models.BooleanField`
        Same idea as `draft_topics`, for the save-all-targets checkbox.
    draft_trigger_gemini_observations : `models.BooleanField`
        Same idea as `draft_topics`, for the trigger-Gemini checkbox.
    draft_handler_code : `models.TextField`
        Same idea as `draft_topics`, for the handler code -- this is the
        main motivating case: a broken handler someone is actively
        editing/debugging should stay visible across navigation, not
        vanish because it never successfully saved.
    draft_error : `models.TextField`
        The validation error message from the failed attempt that
        produced these draft_* fields, if any. Shown in the same danger
        banner used for runtime handler failures (`last_handler_warning`),
        so there's one consistent error presentation regardless of
        whether the failure happened at form-submission time or later at
        runtime in the live consumer.

    """

    topics = models.JSONField(default=list)
    group = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text=(
            "Optional. If left blank, a built-in default group name is "
            "used. Set this explicitly rather than relying on the "
            "underlying client's own default (which falls back to the "
            "machine's hostname), so the consumer group -- and "
            "therefore offset tracking -- stays stable across restarts "
            "and across hosts. Use a brand-new group name to force a "
            "full replay from the earliest available message on the "
            "subscribed topics."
        ),
    )
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
    last_handler_warning = models.TextField(blank=True, default="")
    last_handler_warning_at = models.DateTimeField(null=True, blank=True)
    generation = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    draft_topics = models.TextField(blank=True, default="")
    draft_group = models.CharField(max_length=128, blank=True, default="")
    draft_save_all_targets = models.BooleanField(default=False)
    draft_trigger_gemini_observations = models.BooleanField(default=False)
    draft_handler_code = models.TextField(blank=True, default="")
    draft_error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "ANTARES stream subscription"
        verbose_name_plural = "ANTARES stream subscriptions"

    def __str__(self) -> str:
        return f"ANTARES topics: {', '.join(self.topics)}" if self.topics else "ANTARES topics: (none)"
