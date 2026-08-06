"""
Long-running Dramatiq actor that consumes the ANTARES Kafka alert stream and
maintains the `AntaresLocus` staging table used by the live alert dashboard.

Uses `antares_client.StreamingClient`, which handles the Kafka connection,
SASL auth, and Avro decoding internally and yields `(topic, Locus)` tuples --
so this module only has to translate a `Locus` into a staging-table row.

There is one consumer per `AntaresStreamSubscription`, and each one
authenticates as that subscription's owner using their own stored ANTARES
Kafka credentials (Users -> Manage -> "ANTARES Kafka Stream" in the
Credential Manager). A single Kafka connection authenticates as exactly
one credential, which is why the consumer is per-owner rather than a
single shared process using a superuser's credentials. There is no
`local_settings.py` fallback for credentials, and no fallback to another
user's -- the owner must store their own before their consumer can start.

Everything the consumer needs is read from the subscription row, given
just its primary key: `ingest_antares_stream.send(subscription_id=...,
generation=...)`. There is no `settings.ANTARES_KAFKA_TOPICS` fallback.

(Streaming credentials are issued separately from ANTARES Portal/API
credentials -- contact the ANTARES team to request them.)

KNOWN LIMITATION -- invalid credentials fail silently: the underlying
`confluent_kafka`/`librdkafka` client does not raise a Python exception,
or invoke any registered error callback, when SASL authentication fails
(confirmed against confluentinc/librdkafka#5108 and
confluentinc/confluent-kafka-python#1398, both open/unfixed as of this
writing). A consumer given wrong credentials just retries authentication
forever, completely silently. We work around this with a bounded
first-message timeout (see `STARTUP_SILENCE_WARNING_SECONDS` and the main
polling loop): if nothing is received within that window, we warn (not
stop -- a genuinely quiet topic looks identical from our side, so this is
a best-effort heuristic, not a reliable detector).

This actor runs on its own Dramatiq queue (`ANTARES_QUEUE_NAME`), served
by a dedicated `rundramatiq` process that `goats run` starts alongside the
default one -- no new process *type* is introduced, just a second worker
bound to a different queue. It runs `while True`, polling
`StreamingClient.poll(timeout=...)` directly (not `StreamingClient.iter()`,
which blocks unboundedly and would give us no way to implement the silence
detection above), so it occupies one worker thread for as long as its
subscription is running. Keeping that off the default queue is what stops
a set of long-lived consumers from starving every other GOATS background
task; see `ANTARES_QUEUE_NAME`.
"""

__all__ = ["ingest_antares_stream", "get_antares_kafka_login"]

import logging

import dramatiq
from django.db import transaction

from goats_tom.antares_locus_handler import (
    LocusHandlerError,
    build_rsp_tap_service,
    references_rsp_tap_service,
    is_effectively_blank,
    run_locus_handler,
)
from goats_tom.tasks.trigger_gemini_observation import (
    trigger_gemini_observation_task,
)
from goats_tom.antares_target_save import (
    SaveLocusError,
    save_locus_as_target,
)
from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

# Dedicated Dramatiq queue for the stream consumers, kept off the
# default queue that every other GOATS task uses. Each consumer is a
# `while True` loop with `time_limit=float("inf")`, so it occupies its
# worker thread for as long as ingestion is enabled -- with one
# subscription per user, enough concurrent consumers would fill the
# default pool (started as `--threads 3`, see
# `goats_cli.commands.run.start_background_workers`) and leave nothing
# to run DRAGONS reductions or GOA downloads, which would simply queue
# forever with no visible error. `goats run` starts a second
# `rundramatiq` bound to this queue with its own, much larger thread
# count; consumers block in librdkafka's `poll()`, which releases the
# GIL, so mostly-idle consumer threads are cheap.
ANTARES_QUEUE_NAME = "antares"

# antares_client.stream.StreamingClient prefixes every topic with this
# before subscribing (its own `StreamingClient._TOPIC_PREFIX`), so topics
# coming back from the broker are named e.g.
# "client.young-rubin-transients", while users type/select just
# "young-rubin-transients". Defined here rather than in
# `goats_tom.antares_stream_control` (which imports it from this module)
# because that module already depends on this one -- putting it the other
# way round would be a circular import.
ANTARES_TOPIC_PREFIX = "client."


def strip_topic_prefix(topic: str | None) -> str:
    """Strip ANTARES's internal ``client.`` prefix from a broker topic name.

    Parameters
    ----------
    topic : str or None
        Raw topic name as returned by the Kafka consumer, e.g.
        ``"client.young-rubin-transients"``.

    Returns
    -------
    str
        The topic without the prefix, matching the names shown and
        selected on the ingestion page. Returns ``""`` for `None`, and
        returns the name unchanged if it doesn't carry the prefix.
    """
    if not topic:
        return ""
    if topic.startswith(ANTARES_TOPIC_PREFIX):
        return topic[len(ANTARES_TOPIC_PREFIX) :]
    return topic

# antares_client.stream.StreamingClient.__init__ makes a synchronous
# requests.get() call (fetching its own remote streaming config) BEFORE
# constructing the actual Kafka consumer -- see antares_client's
# stream.py `fetch_config`/`_get_resource`. That HTTP call defaults to a
# 60-second timeout (antares_client.config.config["API_TIMEOUT"]) and is
# NOT interruptible by dramatiq_abort's async-exception mechanism while
# it's blocked: Python can only deliver an async exception the next time
# the thread returns to executing Python bytecode, which doesn't happen
# until the blocking socket call returns or times out. A slow/unresponsive
# ANTARES config endpoint can therefore stall either a new consumer's
# startup, or an old consumer's abort/shutdown, for up to the full 60
# seconds -- confirmed as the likely cause of an observed ~1 minute delay
# before the ingestion page's status caught up, independent of Dramatiq
# worker thread availability. Lowering this to a few seconds means a slow
# endpoint fails fast (raising, which our own error handling already
# surfaces on the ingestion page) instead of silently stalling.
ANTARES_API_TIMEOUT_SECONDS = 10


def _apply_antares_api_timeout() -> None:
    """Lower antares_client's own HTTP request timeout for its internal
    streaming-config fetch, so a slow ANTARES endpoint fails fast instead
    of blocking consumer startup/shutdown for up to a minute.

    Notes
    -----
    `antares_client.config.config` is a plain module-level dict, read
    fresh (not cached) on every `requests.get(..., timeout=...)` call
    inside the library (confirmed by reading `antares_client`'s own
    source), so mutating it here, once, before any `StreamingClient` is
    constructed, is sufficient -- no monkeypatching needed.
    """
    from antares_client.config import config as antares_client_config  # noqa: PLC0415

    antares_client_config["API_TIMEOUT"] = ANTARES_API_TIMEOUT_SECONDS


# How long each individual client.poll(timeout=...) call blocks waiting
# for a message before returning (None, None). Short enough that the
# generation-fencing check (see the main loop) runs frequently, so a
# restart/stop is noticed promptly.
POLL_TIMEOUT_SECONDS = 5

# If zero messages have been received within this many seconds of
# starting, warn (see the main loop's poll-timeout handling) -- this is
# the only available signal for a silently-failed SASL authentication,
# since confluent_kafka/librdkafka does not raise an exception or invoke
# any callback for that failure (see the main loop's comment for the
# confirmed upstream issue references). A legitimately quiet topic is a
# real, valid case this can't be told apart from, so this can false-alarm
# on a genuinely working but low-traffic topic -- 45s balances catching
# real problems reasonably quickly against not firing on every brief,
# normal lull.
STARTUP_SILENCE_WARNING_SECONDS = 45


def _seconds_since(start_time) -> float:
    """Return the number of seconds elapsed since `start_time`.

    Parameters
    ----------
    start_time : datetime.datetime
        A timezone-aware timestamp, e.g. from `django.utils.timezone.now()`.

    Returns
    -------
    float
        Elapsed seconds.
    """
    from django.utils import timezone  # noqa: PLC0415

    return (timezone.now() - start_time).total_seconds()


def get_antares_kafka_login(user):
    """Look up a specific user's stored ANTARES Kafka credentials.

    Parameters
    ----------
    user : `django.contrib.auth.models.User` or None
        The user whose credentials to fetch -- the owner of the
        subscription being started (see
        `goats_tom.models.AntaresStreamSubscription.owner`), or the user
        viewing the ingestion form. `None` returns `None` rather than
        raising, so an orphaned subscription (owner deleted) is reported
        as "no credentials" by the caller.

    Returns
    -------
    `AntaresKafkaLogin` or None
        The credential row, or `None` if `user` is `None` or has not
        stored credentials yet.

    Notes
    -----
    Shared by `_get_streaming_config` (building the consumer's connection
    config) and `fetch_available_topics` (listing topics for the
    ingestion form's dropdown) -- both need the same credentials, so this
    is the single place that decides which user's login to use.

    This previously ignored its caller entirely and always returned the
    *first superuser's* credentials, on the reasoning that the consumer
    was a single shared background process not tied to any user. That no
    longer holds: each subscription is owned by a user and authenticates
    as that user, since one Kafka connection authenticates as exactly one
    credential. Falling back to any other user's credentials would mean
    silently consuming on someone else's ANTARES account.
    """
    from goats_tom.models import AntaresKafkaLogin  # noqa: PLC0415

    if user is None:
        return None
    return AntaresKafkaLogin.objects.filter(user=user).first()


def _get_streaming_config(subscription) -> dict:
    """Build the `StreamingClient` kwargs for one subscription.

    Credentials come from the subscription owner's `AntaresKafkaLogin` row
    (see `goats_tom.views.logins.antares_kafka.AntaresKafkaLoginView`) --
    each subscription authenticates as its own owner, since one Kafka
    connection authenticates as exactly one credential. There is no
    `local_settings.py` fallback for credentials, and no fallback to
    another user's: the owner must store their own via the Credential
    Manager first.

    Parameters
    ----------
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription to build a connection for. Its `topics`,
        `owner`, and `resolved_consumer_group` are all read from the row
        rather than passed separately, so the connection can't drift from
        the stored configuration it's supposed to represent.

    Returns
    -------
    dict
        Keyword arguments for `antares_client.StreamingClient`.

    Raises
    ------
    ValueError
        If the subscription has no topics, or its owner is unset or has
        not stored ANTARES Kafka credentials.
    """
    resolved_topics = list(subscription.topics or [])
    if not resolved_topics:
        raise ValueError(
            "No ANTARES Kafka topics given: `topics` must be a non-empty "
            "list."
        )

    if subscription.owner is None:
        raise ValueError(
            "This ANTARES stream subscription has no owner, so there are "
            "no credentials to connect with. This happens if the owning "
            "user account was deleted; reconfigure the subscription as a "
            "current user to start it again."
        )

    login = get_antares_kafka_login(subscription.owner)

    if login is None:
        raise ValueError(
            f"No ANTARES Kafka credentials found for user "
            f"{subscription.owner.username!r}. Store them via the "
            f"Credential Manager (Users -> Manage -> ANTARES Kafka "
            f"Stream) before starting the consumer."
        )

    return {
        "topics": resolved_topics,
        "api_key": login.api_key,
        "api_secret": login.api_secret,
        "group": subscription.resolved_consumer_group,
    }


def _record_handler_warning(subscription_id: int, message: str) -> None:
    """Save a consumer error to this subscription's row, so it shows up on
    the ingestion page without needing to check server logs.

    Despite the name (kept to avoid a migration renaming the underlying
    `last_handler_warning` field), this covers any failure that stops the
    consumer -- a broken `handler_code`, missing/invalid credentials, or
    any other startup error -- not just handler-code failures. The
    ingestion page's banner label is generic ("Ingestion error") to match.

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription to record the error against.
    message : str
        The error message to display.

    Notes
    -----
    Targets one specific row by primary key. This previously updated
    whichever row had the most recent `updated_at`, which was only ever
    correct while at most one subscription could exist -- with per-user
    subscriptions it would attribute one user's failure to whichever
    user happened to have saved most recently.

    Called at most once per consumer run: with the fail-closed design
    (see `ingest_antares_stream`), any of these failures immediately
    stops the consumer, so there's no "runs many times per run" case to
    optimize for the way there was under the old fail-open design.
    """
    from django.utils import timezone  # noqa: PLC0415

    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    AntaresStreamSubscription.objects.filter(pk=subscription_id).update(
        last_handler_warning=message,
        last_handler_warning_at=timezone.now(),
    )


def _clear_stale_handler_warning(subscription_id: int) -> None:
    """Clear any previously-recorded handler warning on this subscription.

    Called once, right after a new consumer has genuinely started
    (past credential lookup and Kafka connection setup) -- not
    preemptively at form-submission time in
    `goats_tom.antares_stream_control.restart_antares_stream`. Clearing
    early would create a race: if the newly-submitted handler is *also*
    broken, the old error message would be wiped before the new one is
    recorded, leaving a confusing blank state if the page is reloaded in
    between. Clearing only after real startup succeeds means the banner
    reflects either the previous failure (if this run also fails before
    reaching here) or nothing (once a run has genuinely gotten underway).

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription whose warning to clear.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    AntaresStreamSubscription.objects.filter(pk=subscription_id).exclude(
        last_handler_warning=""
    ).update(last_handler_warning="", last_handler_warning_at=None)


def _mark_not_running(subscription_id: int) -> None:
    """Mark this subscription as not running.

    Called when the consumer stops due to a handler failure (fail-closed
    design -- see `ingest_antares_stream`'s docstring), so `is_running`
    accurately reflects reality rather than staying stale-`True` after a
    crash. Aborting/stopping via `goats_tom.antares_stream_control`
    already does this for the deliberate stop/restart paths; this covers
    the case where the consumer stops itself.

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription to mark stopped.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    AntaresStreamSubscription.objects.filter(pk=subscription_id).update(
        is_running=False
    )


def _mark_running(subscription_id: int) -> None:
    """Mark this subscription as running.

    Called by the actor itself, once it has genuinely confirmed startup
    (credentials found, topics resolved) -- not set optimistically by the
    web request in `goats_tom.antares_stream_control.restart_antares_stream`
    before the actor has even run. `ingest_antares_stream.send()` only
    enqueues a message; Dramatiq may not pick it up and run it until some
    time after the web request (and its redirect) has already completed,
    so setting `is_running = True` at submission time was a race: if the
    actor then failed to start (e.g. missing credentials), the page could
    show "Running" -- accurately reflecting the database at page-load time
    -- right alongside the error that had, by then, actually already
    happened but not yet been recorded. Setting it here instead means
    `is_running` only ever reflects genuine, confirmed state.

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription to mark running.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    AntaresStreamSubscription.objects.filter(pk=subscription_id).update(
        is_running=True
    )


def _is_current_generation(subscription_id: int, generation: int) -> bool:
    """Check whether `generation` still matches this subscription's current
    generation in the database -- the fencing-token guarantee against
    consumer clashes.

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription this consumer run belongs to.
    generation : int
        The generation this consumer run was started with.

    Returns
    -------
    bool
        `True` if this consumer is still the current one and should keep
        writing; `False` if it's been superseded by a newer restart/stop
        (or the subscription row was deleted) and should stop immediately
        without writing.

    Notes
    -----
    See `goats_tom.antares_stream_control.advance_generation` for the
    full explanation of why this, not `abort()` timing, is what
    guarantees two consumers never clash: `abort()` is best-effort and
    can't interrupt a blocking C-level Kafka call, so a fixed delay after
    it can only shrink the risk window, never close it. This check, run
    before every write, closes it completely -- an old consumer that
    somehow kept running past a restart/stop will see its generation is
    stale on its very next write attempt and stop there.

    Scoped to a single subscription, so one user restarting their
    consumer cannot stop another user's. Under the previous
    most-recently-updated lookup, *any* user saving a subscription would
    have superseded the generation every other consumer was checking
    against, stopping all of them.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    return AntaresStreamSubscription.objects.filter(
        pk=subscription_id, generation=generation
    ).exists()


def _newest_alert_brightness(locus) -> tuple[float | None, str]:
    """Extract magnitude and passband from the most recent alert.

    Parameters
    ----------
    locus : `antares_client.models.Locus`
        The locus received from the stream.

    Returns
    -------
    tuple
        ``(magnitude, passband)``. Either may be missing -- `None` and ``""``
        respectively -- if the alert does not carry it.

    Notes
    -----
    Read from ``locus.alerts[-1]``, the newest alert, since both describe an
    individual detection rather than the locus as a whole.

    `ant_mag` and `ant_passband` are ANTARES's own normalised properties,
    present regardless of which survey produced the alert -- as opposed to the
    survey-specific keys (ZTF's integer ``fid``, for instance) that would each
    need their own translation.

    Missing values are reported as missing rather than defaulted. They end up
    as the brightness on a real Gemini observation, so a guessed band or
    magnitude is worse than none: without them the template's own brightness
    stands, whereas a wrong one silently misdescribes the target.
    """
    alerts = getattr(locus, "alerts", None) or []
    if not alerts:
        return None, ""

    properties = getattr(alerts[-1], "properties", None) or {}

    magnitude = properties.get("ant_mag")
    try:
        magnitude = float(magnitude) if magnitude is not None else None
    except (TypeError, ValueError):
        magnitude = None

    passband = properties.get("ant_passband") or ""
    return magnitude, str(passband).strip()


def _already_triggered(subscription_id: int, locus_id: str) -> bool:
    """Whether this subscription has already attempted a trigger for this locus.

    Parameters
    ----------
    subscription_id : int
        The subscription in question.
    locus_id : str
        The locus.

    Returns
    -------
    bool
        `True` if a `GeminiTriggerRecord` already exists.

    Notes
    -----
    A cheap pre-check, not the safeguard. The real guarantee is the unique
    constraint on ``(subscription, locus_id)``, enforced when the task reserves
    its record (see `goats_tom.gemini_trigger`). This exists so an active locus
    -- which re-alerts every few minutes -- does not enqueue a task per alert
    only for it to stop immediately.
    """
    from goats_tom.models import GeminiTriggerRecord  # noqa: PLC0415

    return GeminiTriggerRecord.objects.filter(
        subscription_id=subscription_id, locus_id=locus_id
    ).exists()


def _auto_save_already_done(locus_id: str, owner) -> bool:
    """Whether this owner's auto-save for this locus is already complete.

    Parameters
    ----------
    locus_id : str
        The locus in question.
    owner : `django.contrib.auth.models.User` or None
        The subscription owner auto-save is attributed to.

    Returns
    -------
    bool
        `True` only if this owner has a recorded save *and* a target still
        exists for the locus.

    Notes
    -----
    Both conditions are required, and checking only the save record was a bug.
    `AntaresTargetSave` rows are never deleted -- not by clearing the
    dashboard, which removes only `AntaresLocus`, and not by deleting the
    target itself. So a record alone means "this owner saved it at some
    point", which is not the same as "there is a target now". Relying on it
    made auto-save skip a locus permanently once it had been saved and the
    target later removed, with nothing in the interface to explain why.

    Checking only the target would be wrong too: a target created by another
    team still needs sharing with this one, which
    `goats_tom.antares_target_save.save_locus_as_target` does. Requiring both
    means a repeat alert is a cheap no-op, a deleted target is recreated, and
    another team's target is shared.
    """
    from goats_tom.antares_target_save import (  # noqa: PLC0415
        locus_is_saved_as_target,
    )
    from goats_tom.models import AntaresTargetSave  # noqa: PLC0415

    if owner is None:
        return False
    recorded = AntaresTargetSave.objects.filter(
        locus_id=locus_id, saved_by=owner
    ).exists()
    if not recorded:
        return False
    return locus_is_saved_as_target(locus_id)


def _upsert_locus(subscription_id: int, locus, topic: str | None = None) -> None:
    """Create or update the `AntaresLocus` staging row for one locus update.

    Parameters
    ----------
    subscription_id : int
        Primary key of the subscription this row belongs to. Rows are
        unique per ``(subscription, locus_id)``, not per `locus_id`
        alone, so the same locus arriving for two different
        subscriptions produces one row each rather than one row that
        two consumers fight over.
    locus : `antares_client.models.Locus`
        The locus received from the stream.
    topic : str, optional
        The raw Kafka topic this alert arrived on (as returned alongside
        the locus by the consumer). Stored on the row -- with ANTARES's
        internal ``client.`` prefix stripped, see `strip_topic_prefix` --
        as `latest_alert_topic`, so the dashboard can show which
        subscribed topic delivered the most recent alert. A locus can
        appear on several subscribed topics; this records the latest
        one, overwriting on each update, not an accumulated set.

    Notes
    -----
    `locus.alerts` (and its backing `_alerts`) is `None` on stream
    payloads -- confirmed by direct testing against the live stream, not
    just the lazy-load risk noted in earlier code. `alerts` only ever
    populates via a synchronous REST fetch (`Locus._fetch_alerts()`),
    which we deliberately never trigger inside this hot loop.

    `locus.properties`, by contrast, IS always populated on every locus
    update from the stream (it's not one of the lazy-loaded attributes).
    `properties["newest_alert_observation_time"]`, `properties["newest_alert_id"]`,
    and `properties["newest_alert_magnitude"]` were all confirmed against
    a live stream payload or ANTARES' own docs, so those back
    `latest_alert_mjd`, `latest_alert_id`, and `latest_alert_magnitude`
    respectively.

    `locus.catalogs` (plural -- not `catalog_objects`, which IS lazy-loaded)
    is a plain constructor-set list, not one of the three lazy-loaded
    attributes (`alerts`, `catalog_objects`, `lightcurve`), confirmed from
    the antares_client source. `"tns_public_objects" in locus.catalogs`
    backs `in_tns`.
    """
    field_updates = {
        "ra": locus.ra,
        "dec": locus.dec,
        "latest_alert_id": "",
        "latest_alert_mjd": None,
        "latest_alert_magnitude": None,
        "latest_alert_topic": strip_topic_prefix(topic),
        "in_tns": "tns_public_objects" in (locus.catalogs or []),
    }

    newest_alert_mjd = locus.properties.get("newest_alert_observation_time")
    if newest_alert_mjd is not None:
        field_updates["latest_alert_mjd"] = newest_alert_mjd

    newest_alert_magnitude = locus.properties.get("newest_alert_magnitude")
    if newest_alert_magnitude is not None:
        field_updates["latest_alert_magnitude"] = newest_alert_magnitude

    # From the newest alert rather than the locus properties: the Gemini
    # trigger runs later with only ids, so this is the one chance to capture
    # them.
    alert_magnitude, alert_passband = _newest_alert_brightness(locus)
    if alert_passband:
        field_updates["latest_alert_passband"] = alert_passband
    # Preferred over the locus-level `newest_alert_magnitude` when present,
    # since it comes from the same alert as the passband -- pairing a magnitude
    # with a band from a different detection would misreport the brightness.
    if alert_magnitude is not None:
        field_updates["latest_alert_magnitude"] = alert_magnitude

    newest_alert_id = locus.properties.get("newest_alert_id")
    if newest_alert_id is not None:
        field_updates["latest_alert_id"] = newest_alert_id

    with transaction.atomic():
        # Note: no select_for_update() here. Confirmed via Django's own
        # `connection.features.has_select_for_update` (False on SQLite,
        # GOATS's actual production DB backend) that it's a silent no-op
        # there -- Django doesn't add FOR UPDATE to the generated SQL, so
        # it wasn't providing any real protection, only extra overhead.
        # Cross-consumer write safety comes from the generation fencing
        # token (see _is_current_generation), not row locking here. If
        # GOATS ever migrates to Postgres, where select_for_update() is
        # real, revisit whether it's worth adding back for the narrower
        # case of two get_or_create() calls racing on the same locus_id
        # within a single consumer (unlikely, but not impossible under
        # concurrent processing).
        row, created = AntaresLocus.objects.get_or_create(
            subscription_id=subscription_id,
            locus_id=locus.locus_id,
            defaults=field_updates,
        )
        if not created:
            for field, value in field_updates.items():
                setattr(row, field, value)
            row.save(update_fields=list(field_updates.keys()))
    # `last_updated` is refreshed automatically via auto_now on save/create.


@dramatiq.actor(
    queue_name=ANTARES_QUEUE_NAME, max_retries=0, time_limit=float("inf")
)
def ingest_antares_stream(
    subscription_id: int,
    generation: int = 0,
) -> None:
    """Continuously consume the ANTARES Kafka alert stream.

    Blocks indefinitely, receiving loci from `StreamingClient.iter()` and
    upserting rows into `AntaresLocus`. Started either by
    `goats_scheduler.management.commands.run_scheduler` (resuming a
    previously-running `AntaresStreamSubscription` on startup) or by
    submitting the "Ingest from Kafka stream" form (see
    `goats_tom.antares_stream_control.restart_antares_stream`). Not
    started from `AppConfig.ready()`, which would fire in every process
    and enqueue duplicate consumers.

    `time_limit=float("inf")` disables Dramatiq's default 10-minute actor
    time limit. Without this, Dramatiq forcibly kills the worker thread
    after the default timeout, since this actor is designed to never
    return under normal operation.

    Parameters
    ----------
    subscription_id : int
        Primary key of the `AntaresStreamSubscription` to consume for.
        Every other input -- topics, handler code, consumer group,
        auto-save setting, and the owning user whose credentials to
        authenticate with -- is read from that row here rather than
        passed as separate actor arguments. Reading them in one place
        means the running consumer cannot drift from the stored
        configuration it is supposed to represent, and it makes the
        actor's arguments independent of how many settings the
        subscription grows.

        Safe against the row changing between `send()` and the actor
        actually starting: any change that matters goes through
        `goats_tom.antares_stream_control`, which advances
        `generation` and starts a fresh consumer, so a stale run stops
        at its first generation check (see `generation` below).
    generation : int, optional
        Fencing token: the subscription's generation number at the time
        this consumer was started (see
        `goats_tom.antares_stream_control.advance_generation`). Checked
        before every write against *this subscription's* current
        generation; if it has moved past this value (because a newer
        restart/stop happened for this same subscription), this
        consumer stops immediately without writing, guaranteeing it
        can never clash with a newer consumer even if its `abort()`
        signal was delayed or lost.

    Raises
    ------
    ValueError
        If the subscription no longer exists, has no topics, or its
        owner has no stored ANTARES Kafka credentials (see
        `_get_streaming_config`).
    LocusHandlerError
        If `handler_code` raises or returns a non-bool value against a
        real locus from the stream. Stops the consumer (see above).
    """
    from antares_client import StreamingClient  # noqa: PLC0415
    from dramatiq_abort import Abort  # noqa: PLC0415

    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    _apply_antares_api_timeout()

    # Read the whole configuration from the row, in one place, rather than
    # trusting actor arguments that may no longer match it. `select_related`
    # so the owner (whose credentials authenticate this connection) comes
    # back in the same query.
    subscription = (
        AntaresStreamSubscription.objects.select_related("owner")
        .filter(pk=subscription_id)
        .first()
    )
    if subscription is None:
        # Nothing to record the failure against -- the row this consumer
        # exists to serve is gone, so there is no page to surface an error
        # on. Log and stop rather than raising into Dramatiq's
        # unhandled-exception path, since a deleted subscription is a
        # legitimate way for a queued consumer to become obsolete.
        logger.warning(
            "ANTARES stream subscription id=%s no longer exists; not "
            "starting a consumer for it.",
            subscription_id,
        )
        return

    topics = list(subscription.topics or [])
    handler_code = subscription.handler_code
    save_all_targets = subscription.save_all_targets
    trigger_gemini_observations = subscription.trigger_gemini_observations
    owner = subscription.owner
    # Resolved once here, not per locus: auto-saved targets are shared with
    # the owner's team so the whole group sees them, and this costs a query.
    owner_pi_group = getattr(owner, "antares_pi_group", None)
    owner_group = owner_pi_group.group if owner_pi_group is not None else None

    if handler_code and is_effectively_blank(handler_code):
        logger.info(
            "handler_code is effectively blank (comments/whitespace "
            "only); treating as no handler."
        )
        handler_code = None

    try:
        config = _get_streaming_config(subscription)
    except ValueError as exc:
        # A startup failure (e.g. missing/invalid credentials, no topics)
        # happens before the consumer ever connects -- previously this
        # propagated uncaught, leaving the subscription's `is_running`
        # stuck at True (set synchronously when the form was submitted,
        # before this actor even started) even though nothing was
        # actually running. Mark it stopped and surface the error the
        # same way a handler failure would, so the ingestion page
        # reflects reality instead of silently showing "Running" forever.
        logger.error("ANTARES Kafka consumer failed to start: %s", exc)
        _record_handler_warning(
            subscription_id, f"Consumer failed to start: {exc}"
        )
        _mark_not_running(subscription_id)
        raise

    logger.info(
        "ANTARES Kafka consumer started for subscription id=%s "
        "topics=%s group=%r.",
        subscription_id,
        config["topics"],
        config["group"],
    )
    _mark_running(subscription_id)
    _clear_stale_handler_warning(subscription_id)

    # Built once here, not per message. The client is identical for every
    # locus in this run (same configuring user, same token), but
    # constructing it costs a DB lookup plus a real HTTP request to the
    # TAP /capabilities endpoint -- doing that per incoming alert was
    # significant wasted work against Rubin's servers. Only built at all
    # if the handler genuinely references it (same AST check the handler
    # runner uses), so handlers that don't touch TAP pay nothing.
    #
    # Consequence worth knowing: a token changed mid-run isn't picked up
    # until ingestion is restarted, since this instance is reused for the
    # life of the loop.
    rsp_tap_service = None
    if handler_code and references_rsp_tap_service(handler_code):
        rsp_tap_service = build_rsp_tap_service(owner)
        logger.info(
            "Built RSP TAP client for this consumer run (available=%s).",
            rsp_tap_service is not None,
        )

    try:
        with StreamingClient(
            config["topics"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
            group=config["group"],
        ) as client:
            from django.utils import timezone  # noqa: PLC0415

            consumer_started_at = timezone.now()
            received_first_message = False
            warned_about_silence = False
            while True:
                if not _is_current_generation(subscription_id, generation):
                    logger.info(
                        "Generation %d superseded for subscription "
                        "id=%s; stopping consumer for topics=%s.",
                        generation,
                        subscription_id,
                        topics,
                    )
                    break

                # client.poll(timeout=N) returns (None, None) if N seconds
                # elapse with nothing received -- used instead of
                # client.iter() (which blocks unboundedly with no way to
                # detect a stuck consumer) specifically because
                # confluent_kafka/librdkafka does not raise a Python
                # exception, or invoke any registered callback, when SASL
                # authentication fails (confirmed: this is a known, still-
                # open upstream limitation -- see
                # confluentinc/librdkafka#5108 and
                # confluentinc/confluent-kafka-python#1398). A consumer
                # given wrong credentials just retries authentication
                # forever, completely silently: no exception, no error
                # callback, nothing our own try/except could ever catch.
                # We have no reliable way to distinguish that from a
                # genuinely quiet topic, so this is a best-effort signal,
                # not a guarantee: after STARTUP_SILENCE_WARNING_SECONDS
                # with zero messages received since starting, warn once
                # (not stop -- the topic may simply be quiet) so the
                # operator has *something* to go on instead of an
                # indefinitely stuck "Running" status with no explanation.
                topic, locus = client.poll(timeout=POLL_TIMEOUT_SECONDS)

                if topic is None and locus is None:
                    if (
                        not received_first_message
                        and not warned_about_silence
                        and _seconds_since(consumer_started_at)
                        >= STARTUP_SILENCE_WARNING_SECONDS
                    ):
                        logger.warning(
                            "No messages received on topics=%s within %d "
                            "seconds of starting. May mean credentials are "
                            "being silently rejected (see module "
                            "docstring's KNOWN LIMITATION), or the "
                            "topic(s) are simply quiet. Not stopped "
                            "automatically.",
                            topics,
                            STARTUP_SILENCE_WARNING_SECONDS,
                        )
                        _record_handler_warning(
                            subscription_id,
                            f"No messages received on topics={topics} "
                            f"within {STARTUP_SILENCE_WARNING_SECONDS}s. "
                            f"Possibly invalid credentials (ANTARES's Kafka "
                            f"client doesn't report bad credentials as an "
                            f"error) or just a quiet topic. Still running. "
                            f"If you expect activity, double-check your "
                            f"credentials."
                        )
                        warned_about_silence = True
                    continue

                received_first_message = True
                if warned_about_silence:
                    # Real data arrived after all -- clear the warning
                    # rather than leave a stale "might be broken" message
                    # once we have direct evidence it's actually working.
                    _clear_stale_handler_warning(subscription_id)
                    warned_about_silence = False

                if handler_code:
                    try:
                        keep = run_locus_handler(
                            handler_code,
                            locus,
                            rsp_tap_service=rsp_tap_service,
                            # So `dashboard_locus_count()` reports this
                            # dashboard's rows, not every subscription's.
                            subscription_id=subscription_id,
                        )
                    except LocusHandlerError as exc:
                        logger.error(
                            "User-defined locus handler failed for locus_id=%s; "
                            "stopping the consumer.",
                            getattr(locus, "locus_id", None),
                        )
                        _record_handler_warning(
                            subscription_id,
                            f"{exc}\n\nHandler code:\n{handler_code}",
                        )
                        _mark_not_running(subscription_id)
                        raise
                    if not keep:
                        continue

                try:
                    _upsert_locus(subscription_id, locus, topic)

                    # Skipped only when this owner has a recorded save AND
                    # a target still exists -- see `_auto_save_already_done`.
                    # Checking either alone is wrong: the record outlives the
                    # target, and the target may belong to another team who
                    # saved it first.
                    if save_all_targets and not _auto_save_already_done(
                        locus.locus_id, owner
                    ):
                        try:
                            save_locus_as_target(
                                locus.locus_id,
                                saved_by=owner,
                                share_with_group=owner_group,
                            )
                        except SaveLocusError:
                            logger.exception(
                                "Auto-save failed for locus_id=%s; ingestion "
                                "continues.",
                                locus.locus_id,
                            )

                    # Considered independently of whether *this* alert did the
                    # saving. Nesting it under the save was wrong: a locus
                    # already saved -- by an earlier run, by hand, or by
                    # another team whose target we merely gained access to --
                    # skips the save, and so could never trigger. Enabling
                    # triggering on an already-populated dashboard did nothing
                    # at all for the same reason.
                    #
                    # Triggering has its own idempotency: GeminiTriggerRecord
                    # is unique per (subscription, locus), so a locus can only
                    # ever trigger once for this subscription regardless of
                    # how many alerts arrive.
                    #
                    # Enqueued, never called inline. Creating an observation
                    # takes several GPP round trips (allocation, target, clone,
                    # then polling for the workflow state), which would stall
                    # ingestion for every alert -- and a GPP outage would stop
                    # the stream rather than just the triggering.
                    if trigger_gemini_observations and not _already_triggered(
                        subscription_id, locus.locus_id
                    ):
                        trigger_gemini_observation_task.send(
                            subscription_id=subscription_id,
                            locus_id=locus.locus_id,
                        )
                except Exception:
                    logger.exception(
                        "Failed to process ANTARES locus update: topic=%s "
                        "locus_id=%s",
                        topic,
                        getattr(locus, "locus_id", None),
                    )
    except Abort:
        # A deliberate stop/restart (see
        # goats_tom.antares_stream_control._abort_running_consumer) --
        # not a real failure. Caught here and logged calmly rather than
        # left to propagate: Dramatiq's own Retries middleware logs any
        # exception that escapes the actor as an unhandled-exception
        # traceback (ERROR level, full stack trace), which looks like a
        # crash even though this is the intended, expected way stopping
        # ingestion works. Not re-raised: max_retries=0 on this actor
        # means Dramatiq's retry bookkeeping doesn't do anything useful
        # with the distinction between "raised" and "returned normally"
        # here anyway, and our own state tracking (is_running,
        # generation) is handled explicitly by our own code, not by
        # Dramatiq's success/failure signal.
        logger.info("ANTARES Kafka consumer aborted (stop or restart requested).")
        return
    except LocusHandlerError:
        # Already recorded/marked not-running at the raise site above;
        # just let it propagate to Dramatiq as a real failure.
        raise
    except Exception as exc:
        # Any other failure -- most notably StreamingClient(...) itself
        # rejecting the connection (e.g. the broker rejects credentials
        # that passed our own validation, or a network failure) -- is a
        # real problem, not a deliberate stop. Same fix as the
        # config-resolution failure above: without this, is_running would
        # stay stuck at True (set when the form was submitted, before
        # this actor started) even though the consumer never actually
        # connected.
        logger.exception("ANTARES Kafka consumer failed unexpectedly.")
        _record_handler_warning(
            subscription_id, f"Consumer failed unexpectedly: {exc}"
        )
        _mark_not_running(subscription_id)
        raise

    logger.info("ANTARES Kafka consumer stopped.")
