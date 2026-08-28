"""Module for `AntaresStreamSubscription` model."""

__all__ = ["AntaresStreamSubscription"]

from django.conf import settings
from django.db import models

# Default lifetime cap on automatic Gemini triggers. Low on purpose: each
# trigger spends real telescope time, and the cap is the backstop if the
# allocation check is somehow unavailable.
DEFAULT_MAX_TRIGGERS = 10

#: Loci kept on the dashboard before ingestion stops, when the user leaves the
#: field at its default. A bound rather than a target: `cleanup_stale_antares_loci`
#: already discards rows that stop updating, so this exists to stop a handler
#: that filters nothing from filling the table, not to ration normal use.
DEFAULT_MAX_LOCI = 100


class AntaresStreamSubscription(models.Model):
    """One user's ANTARES Kafka stream subscription and its dashboard.

    There is one row per owning user (enforced by `owner` being a
    `OneToOneField`), and each row backs exactly one locus dashboard --
    see `goats_tom.models.AntaresLocus.subscription`. Rows are looked up
    by primary key or by owner, never by "whichever was updated most
    recently": an earlier version of this model was a de facto singleton,
    with every state transition resolving "the current subscription" as
    ``objects.order_by("-updated_at").first()``, which cannot express more
    than one concurrently-configured subscription.

    Attributes
    ----------
    owner : `models.OneToOneField`
        The user this subscription belongs to. Their stored
        `goats_tom.models.AntaresKafkaLogin` credentials are what the
        consumer authenticates with (one Kafka connection authenticates
        as exactly one credential, which is why there is one consumer per
        owner), and their personal RSP/GPP credentials are what
        `handler_code` and observation triggering act as -- these are
        per-researcher accounts, not shared ones, so the consumer must
        know whose identity to use rather than falling back to a
        superuser's.

        `SET_NULL` on delete rather than cascading, so deleting a user
        account doesn't delete the subscription row (and, transitively,
        its ingested loci) -- it just orphans it. An orphaned row cannot
        start a consumer, since there are no credentials to authenticate
        with, and should be reported as such rather than silently falling
        back to another user's credentials.

        Replaces an earlier `configured_by` field, which recorded the
        user who most recently submitted the ingestion form. With one
        subscription per user, "the owner" and "whoever configured it"
        are necessarily the same person, so two fields holding the same
        value was a source of confusion rather than information.
    topics : `models.JSONField`
        List of Kafka topic names to subscribe to, e.g.
        ``["extragalactic_staging", "nuclear_transient_staging"]``.
    consumer_group : `models.CharField`
        Optional *suffix* for this subscription's Kafka consumer group
        name. The effective name is always derived, never used verbatim
        -- see `resolved_consumer_group` for why, which is a correctness
        issue rather than a naming preference.

        Named `consumer_group` rather than `group` (its original name) to
        keep it distinct from `django.contrib.auth.models.Group`, which
        this feature also uses for per-PI access control. The two are
        entirely unrelated, and the collision was actively misleading.
    save_all_targets : `models.BooleanField`
        Whether all ingested loci should be saved as GOATS targets.
    trigger_gemini_observations : `models.BooleanField`
        Whether ingested loci should automatically trigger Gemini
        observations, by cloning `gpp_observation_id` onto each newly-saved
        locus (see `goats_tom.gemini_trigger`).
    gpp_program_id : `models.CharField`
        The GPP program the template observation belongs to. Stored alongside
        the observation id because the allocation check is per-program, and
        looking it up from the observation on every trigger would be an extra
        round trip per alert.
    gpp_observation_id : `models.CharField`
        The GPP observation used as a template. Triggering clones it and
        points the clone at the new target, which is how a ToO is normally
        set up by hand -- so the PI configures instrument, exposure and
        conditions in Explore, where those tools already exist, rather than
        GOATS reimplementing them.
    gpp_observation_overrides : `models.JSONField`
        Observation properties to apply to each clone, overriding what the
        template carries. Empty means the template is used as it stands.

        Applied to the *clone* rather than saved back to the template, through
        GPP's own `CloneObservationInput.set_`. The template belongs to a real
        programme and may be used by other observations or by hand, so
        adjusting it for the sake of ANTARES triggering would change something
        outside this subscription's scope.

        Stored as GPP's own property shape, already validated by
        `goats_tom.serializers.gpp.ObservationSerializer`, so a malformed
        override cannot reach trigger time and fail once per alert.
    run_number : `models.PositiveIntegerField`
        Counts ingestion *runs*. Incremented only when a run starts, unlike
        `generation`, which also advances on stop so that a stopped consumer
        is fenced off. Gemini trigger records and the trigger cap are scoped
        to this, so stopping ingestion leaves the run's results on the
        dashboard and only starting again clears them.
    gpp_target_id : `models.CharField`
        The template observation's target in GPP. Cloned for each new locus so
        the created target inherits the template's source profile -- including
        its SED, which cannot be reconstructed from an alert.
    gpp_target_overrides : `models.JSONField`
        Target properties from the template picker, as a GPP
        `TargetPropertiesInput` dump. The companion to
        `gpp_observation_overrides`; without it the picker's target-side
        configuration was collected and then discarded.
    gpp_instrument : `models.CharField`
        The template's instrument, needed to record the created observation in
        GOATS the way the interactive path does.
    gpp_workflow_state : `models.CharField`
        Workflow state to set on each created observation. Blank means
        ``READY``.

        Taken from the template editor's own State field, so an observation
        can be created for review rather than made immediately observable.
        Forcing ``READY`` regardless -- as an earlier version did -- silently
        discarded a choice the interface presented as editable.
    max_triggers : `models.PositiveIntegerField`
        Lifetime cap on how many observations this subscription may create.
        `None` means no limit. Defaults to
        `DEFAULT_MAX_TRIGGERS`, deliberately low: automatic triggering spends
        real telescope time from a live alert stream, and a broad topic could
        otherwise consume a programme's allocation overnight.

        A total rather than a nightly quota, so reaching it stops triggering
        until the number is raised. That is a deliberate stop, not a failure,
        and is reported as such on the dashboard -- ingestion continues either
        way.
    handler_code : `models.TextField`
        Optional user-defined ``def myfilter(locus): ...`` function run
        against each locus before it's saved, acting as an additional
        filter on top of the topic subscription. See
        `goats_tom.antares_locus_handler` for the execution model and its
        restrictions. Validated with a real dry run at submission time;
        if it still fails against a real locus from the stream, this
        subscription's consumer stops entirely (fail-closed) rather than
        skipping that locus and continuing.
    dramatiq_message_id : `models.CharField`
        Message ID of the currently-running `ingest_antares_stream`
        actor invocation, if any. Used to abort the running consumer
        before starting a new one with updated topics.
    is_running : `models.BooleanField`
        Whether a consumer is believed to currently be running for this
        subscription. Set to `False` both by deliberate stop/restart
        actions and by the consumer itself if `handler_code` fails.
    last_handler_warning : `models.TextField`
        The error from `handler_code` that stopped this subscription's
        consumer, if any, including the handler source itself. Shown on
        the ingestion page so a broken filter is visible without checking
        server logs. Cleared the next time a (new) consumer is
        successfully started.
    last_handler_warning_at : `models.DateTimeField`
        When `last_handler_warning` was last set.
    generation : `models.PositiveIntegerField`
        Incremented every time a new consumer is started for this
        subscription (restart or stop). Passed into
        `ingest_antares_stream` as the generation it was started with;
        the actor checks, before every write, that its generation still
        matches *this row's* current generation in the database, and
        stops immediately if not. This is a fencing token: it guarantees
        an old, not-yet-fully-stopped consumer can never write data after
        a newer one has started for the same subscription, closing the
        window that a fixed delay after `abort()` could only shrink, not
        eliminate (`dramatiq_abort` can't interrupt a blocking C-level
        Kafka call, and provides no way to confirm a specific message has
        actually stopped).

        Scoped per row, so one user restarting their consumer has no
        effect on any other user's.
    updated_at : `models.DateTimeField`
        When this subscription was last changed. Informational only --
        deliberately not used to identify "the current" subscription (see
        the class docstring).
    draft_topics : `models.TextField`
        The raw (unparsed, possibly malformed) topics text from the most
        recent form submission that FAILED validation, if any. Separate
        from `topics` (which only reflects the last successfully-started
        consumer) so a failed attempt's typed values survive navigating
        away and back, until either a successful submission (which clears
        all draft_* fields) or the user explicitly starts over.
    draft_consumer_group : `models.CharField`
        Same idea as `draft_topics`, for the consumer group field.
    draft_save_all_targets : `models.BooleanField`
        Same idea as `draft_topics`, for the save-all-targets checkbox.
    draft_trigger_gemini_observations : `models.BooleanField`
        Same idea as `draft_topics`, for the trigger-Gemini checkbox.
    draft_handler_code : `models.TextField`
        Same idea as `draft_topics`, for the handler code -- this is the
        main motivating case: a broken handler someone is actively
        editing/debugging should stay visible across navigation, not
        vanish because it never successfully saved.
    draft_error_at : `models.DateTimeField`
        When `draft_error` was last set. Shown alongside the error in the
        banner, matching how `last_handler_warning_at` is shown for
        runtime failures -- without it a validation error appears with no
        indication of when it happened, so it's impossible to tell a
        fresh failure from a stale one.
    draft_error : `models.TextField`
        The validation error message from the failed attempt that
        produced these draft_* fields, if any. Shown in the same danger
        banner used for runtime handler failures (`last_handler_warning`),
        so there's one consistent error presentation regardless of
        whether the failure happened at form-submission time or later at
        runtime in the live consumer.

    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antares_subscription",
    )
    topics = models.JSONField(default=list)
    consumer_group = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text=(
            "Optional. Appended to an automatically-generated, "
            "per-subscription consumer group name; leave blank to use "
            "that generated name on its own. Set a new value to force a "
            "full replay from the earliest available message on the "
            "subscribed topics, which is what a brand-new consumer "
            "group name does. Note this is a suffix, not the whole "
            "name: the generated prefix is always applied, so your "
            "consumer group can never collide with another user's."
        ),
    )
    save_all_targets = models.BooleanField(default=False)
    trigger_gemini_observations = models.BooleanField(default=False)
    gpp_program_id = models.CharField(max_length=128, blank=True, default="")
    gpp_observation_id = models.CharField(max_length=128, blank=True, default="")
    gpp_observation_overrides = models.JSONField(default=dict, blank=True)
    gpp_workflow_state = models.CharField(max_length=32, blank=True, default="")
    gpp_target_id = models.CharField(max_length=128, blank=True, default="")
    gpp_target_overrides = models.JSONField(default=dict, blank=True)
    gpp_instrument = models.CharField(max_length=64, blank=True, default="")
    max_loci = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Stop ingesting once the dashboard holds this many loci. Blank "
            "for no limit."
        ),
    )
    max_triggers = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=DEFAULT_MAX_TRIGGERS,
        help_text=(
            "Maximum number of Gemini observations this subscription may "
            "create in total. Leave blank for no limit."
        ),
    )
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
    # Whether the last notice reports a fault or a normal outcome.
    #
    # The banner previously inferred this from `is_running`: any stopped
    # subscription with a message showed it in red as an "Ingestion error".
    # That was right for a crash and wrong for reaching a loci limit the
    # user set themselves, which is the system doing exactly as asked.
    # Defaults to True so every existing caller keeps reporting faults as
    # faults without being touched.
    last_handler_warning_is_error = models.BooleanField(default=True)
    generation = models.PositiveIntegerField(default=0)
    run_number = models.PositiveIntegerField(default=0, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    draft_topics = models.TextField(blank=True, default="")
    draft_consumer_group = models.CharField(max_length=128, blank=True, default="")
    draft_save_all_targets = models.BooleanField(default=False)
    draft_trigger_gemini_observations = models.BooleanField(default=False)
    draft_handler_code = models.TextField(blank=True, default="")
    draft_error = models.TextField(blank=True, default="")
    draft_error_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "ANTARES stream subscription"
        verbose_name_plural = "ANTARES stream subscriptions"

    # Prefix for every generated consumer group name. Changing this
    # invalidates every existing consumer's committed offsets (a new group
    # name means Kafka has no offset for it, so consumption restarts from
    # the earliest available message), so it should be treated as stable.
    CONSUMER_GROUP_PREFIX = "goats-antares"

    @property
    def resolved_consumer_group(self) -> str:
        """The Kafka consumer group name this subscription must use.

        Returns
        -------
        str
            ``"goats-antares-<pk>"``, with ``"-<consumer_group>"``
            appended if `consumer_group` is set.

        Notes
        -----
        The primary key is always included, and user input is only ever a
        suffix, because two subscriptions sharing a consumer group name
        is a silent data-loss bug rather than a cosmetic clash. Kafka
        treats same-named consumers as one consumer group and balances
        partitions *between* them, so each subscription would receive
        only an arbitrary subset of the alerts on its topics -- with no
        error, no warning, and nothing in the logs to indicate it. The
        dashboard would simply be missing loci.

        Deriving from the primary key rather than the owner's username
        keeps the name stable across a username change, which would
        otherwise silently reset that subscription's offsets.

        This replaced a module-level `DEFAULT_GROUP` constant shared by
        every consumer, which was safe only while at most one
        subscription could exist at a time.
        """
        base = f"{self.CONSUMER_GROUP_PREFIX}-{self.pk}"
        suffix = (self.consumer_group or "").strip()
        return f"{base}-{suffix}" if suffix else base

    def __str__(self) -> str:
        who = self.owner.username if self.owner else "unowned"
        topics = ", ".join(self.topics) if self.topics else "(none)"
        return f"ANTARES subscription for {who}: {topics}"
