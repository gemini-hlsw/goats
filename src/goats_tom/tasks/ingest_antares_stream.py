"""
Long-running Dramatiq actor that consumes the ANTARES Kafka alert stream and
maintains the `AntaresLocus` staging table used by the live alert dashboard.

Uses `antares_client.StreamingClient`, which handles the Kafka connection,
SASL auth, and Avro decoding internally and yields `(topic, Locus)` tuples --
so this module only has to translate a `Locus` into a staging-table row.

Credentials come from the first superuser's stored ANTARES Kafka
credentials (Users -> Manage -> "ANTARES Kafka Stream" in the Credential
Manager), since the consumer is a single shared background process, not
tied to any particular request/user. There is no `local_settings.py`
fallback for credentials -- a superuser must store them via the
Credential Manager before the consumer can start.

Topics are passed explicitly via `ingest_antares_stream.send(topics=[...])`
(from the "Ingest from Kafka stream" form, or from the scheduler resuming
a previously-running subscription on startup). There is no
`settings.ANTARES_KAFKA_TOPICS` fallback.

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

This actor is intended to run inside the existing `rundramatiq` worker
process that GOATS already starts via `goats run` -- no new process type is
introduced. It runs `while True`, polling `StreamingClient.poll(timeout=...)`
directly (not `StreamingClient.iter()`, which blocks unboundedly and would
give us no way to implement the silence detection above), so it occupies
one Dramatiq worker thread/process for the lifetime of the app.
"""

__all__ = ["ingest_antares_stream"]

import logging

import dramatiq
from django.db import transaction

from goats_tom.antares_locus_handler import (
    LocusHandlerError,
    is_effectively_blank,
    run_locus_handler,
)
from goats_tom.antares_target_save import (
    SaveLocusError,
    locus_is_saved_as_target,
    save_locus_as_target,
)
from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

DEFAULT_GROUP = "goats-antares-locus-dashboard"

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
# confirmed upstream issue references). Deliberately generous, since a
# legitimately quiet topic is a real, valid case this can't be told apart
# from -- this trades slower detection for fewer false alarms.
STARTUP_SILENCE_WARNING_SECONDS = 120


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


def _get_streaming_config(topics: list[str], group: str | None = None) -> dict:
    """Build the `StreamingClient` kwargs from an explicit topic list,
    optional group name, and stored ANTARES Kafka credentials.

    Credentials come exclusively from the first superuser's
    `AntaresKafkaLogin` row (see
    `goats_tom.views.logins.antares_kafka.AntaresKafkaLoginView`), since
    the consumer is a single shared background process, not tied to any
    particular request/user. There is no `local_settings.py` fallback for
    credentials -- a superuser must store them via the Credential Manager
    first.

    Parameters
    ----------
    topics : list of str
        Topics to subscribe to, e.g. passed in by
        `ingest_antares_stream.send(topics=[...])` from a form submission.
        Required -- there is no `settings.ANTARES_KAFKA_TOPICS` fallback.
    group : str, optional
        Kafka consumer group name, set on the ingestion page (see
        `goats_tom.models.AntaresStreamSubscription.group`). Falls back
        to `DEFAULT_GROUP` if not given or blank.

    Returns
    -------
    dict
        Keyword arguments for `antares_client.StreamingClient`.

    Raises
    ------
    ValueError
        If `topics` is empty, no superuser exists, or no superuser has
        stored ANTARES Kafka credentials.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    from goats_tom.models import AntaresKafkaLogin  # noqa: PLC0415

    resolved_topics = list(topics or [])
    if not resolved_topics:
        raise ValueError(
            "No ANTARES Kafka topics given: `topics` must be a non-empty "
            "list."
        )

    User = get_user_model()
    superuser = User.objects.filter(is_superuser=True).order_by("pk").first()
    login = (
        AntaresKafkaLogin.objects.filter(user=superuser).first()
        if superuser
        else None
    )

    if login is None:
        raise ValueError(
            "No ANTARES Kafka credentials found. A superuser must store "
            "them via the Credential Manager (Users -> Manage -> ANTARES "
            "Kafka Stream) before the consumer can start."
        )

    return {
        "topics": resolved_topics,
        "api_key": login.api_key,
        "api_secret": login.api_secret,
        "group": group or DEFAULT_GROUP,
    }


def _record_handler_warning(message: str) -> None:
    """Save a consumer error to the current subscription row, so it shows
    up on the ingestion page without needing to check server logs.

    Despite the name (kept to avoid a migration renaming the underlying
    `last_handler_warning` field), this covers any failure that stops the
    consumer -- a broken `handler_code`, missing/invalid credentials, or
    any other startup error -- not just handler-code failures. The
    ingestion page's banner label is generic ("Ingestion error") to match.

    Parameters
    ----------
    message : str
        The error message to display.

    Notes
    -----
    Updates the most recently-updated `AntaresStreamSubscription` row --
    same "current subscription" lookup used throughout this feature (see
    `goats_tom.antares_stream_control`), since only one subscription is
    meant to be active at a time.

    Called at most once per consumer run: with the fail-closed design
    (see `ingest_antares_stream`), any of these failures immediately
    stops the consumer, so there's no "runs many times per run" case to
    optimize for the way there was under the old fail-open design.
    """
    from django.utils import timezone  # noqa: PLC0415

    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is None:
        return
    subscription.last_handler_warning = message
    subscription.last_handler_warning_at = timezone.now()
    subscription.save(
        update_fields=["last_handler_warning", "last_handler_warning_at"]
    )


def _clear_stale_handler_warning() -> None:
    """Clear any previously-recorded handler warning, if one is set.

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
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is not None and subscription.last_handler_warning:
        subscription.last_handler_warning = ""
        subscription.last_handler_warning_at = None
        subscription.save(
            update_fields=["last_handler_warning", "last_handler_warning_at"]
        )


def _mark_not_running() -> None:
    """Mark the current subscription as not running.

    Called when the consumer stops due to a handler failure (fail-closed
    design -- see `ingest_antares_stream`'s docstring), so `is_running`
    accurately reflects reality rather than staying stale-`True` after a
    crash. Aborting/stopping via `goats_tom.antares_stream_control`
    already does this for the deliberate stop/restart paths; this covers
    the case where the consumer stops itself.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is not None:
        subscription.is_running = False
        subscription.save(update_fields=["is_running"])


def _mark_running() -> None:
    """Mark the current subscription as running.

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
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is not None:
        subscription.is_running = True
        subscription.save(update_fields=["is_running"])


def _is_current_generation(generation: int) -> bool:
    """Check whether `generation` still matches the subscription's current
    generation in the database -- the fencing-token guarantee against
    consumer clashes.

    Parameters
    ----------
    generation : int
        The generation this consumer run was started with.

    Returns
    -------
    bool
        `True` if this consumer is still the current one and should keep
        writing; `False` if it's been superseded by a newer restart/stop
        and should stop immediately without writing.

    Notes
    -----
    See `goats_tom.antares_stream_control._advance_generation` for the
    full explanation of why this, not `abort()` timing, is what
    guarantees two consumers never clash: `abort()` is best-effort and
    can't interrupt a blocking C-level Kafka call, so a fixed delay after
    it can only shrink the risk window, never close it. This check, run
    before every write, closes it completely -- an old consumer that
    somehow kept running past a restart/stop will see its generation is
    stale on its very next write attempt and stop there.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    return subscription is not None and subscription.generation == generation


def _upsert_locus(locus) -> None:
    """Create or update the `AntaresLocus` staging row for one locus update.

    Parameters
    ----------
    locus : `antares_client.models.Locus`
        The locus received from the stream.

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
    `properties["num_alerts"]`, and `properties["newest_alert_magnitude"]`
    were all confirmed against a live stream payload or ANTARES' own docs,
    so those back `latest_alert_mjd`, `latest_alert_id`, `alert_count`, and
    `latest_alert_magnitude` respectively. `alert_count` uses ANTARES' own
    running total rather than a locally-incremented counter, since a local
    counter would drift from reality if this consumer ever missed messages.

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
        "in_tns": "tns_public_objects" in (locus.catalogs or []),
    }

    newest_alert_mjd = locus.properties.get("newest_alert_observation_time")
    if newest_alert_mjd is not None:
        field_updates["latest_alert_mjd"] = newest_alert_mjd

    newest_alert_magnitude = locus.properties.get("newest_alert_magnitude")
    if newest_alert_magnitude is not None:
        field_updates["latest_alert_magnitude"] = newest_alert_magnitude

    newest_alert_id = locus.properties.get("newest_alert_id")
    if newest_alert_id is not None:
        field_updates["latest_alert_id"] = newest_alert_id

    # Use ANTARES' own authoritative count rather than incrementing locally,
    # since a local counter drifts from reality if this consumer ever misses
    # messages (restarts, consumer group rebalances, downtime).
    num_alerts = locus.properties.get("num_alerts")
    alert_count = num_alerts if num_alerts is not None else 1
    field_updates["alert_count"] = alert_count

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
            locus_id=locus.locus_id,
            defaults=field_updates,
        )
        if not created:
            for field, value in field_updates.items():
                setattr(row, field, value)
            row.save(update_fields=list(field_updates.keys()))
    # `last_updated` is refreshed automatically via auto_now on save/create.


@dramatiq.actor(max_retries=0, time_limit=float("inf"))
def ingest_antares_stream(
    topics: list[str],
    handler_code: str | None = None,
    save_all_targets: bool = False,
    group: str | None = None,
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
    topics : list of str
        Topics to subscribe to. Required -- there is no settings-based
        fallback.
    handler_code : str, optional
        User-defined function body run against each locus before it's
        upserted, as an additional filter. See
        `goats_tom.antares_locus_handler.run_locus_handler`. Validated at
        submission time (see
        `goats_tom.antares_locus_handler.validate_handler_code`) with a
        real dry run against a test locus, so most bugs never reach here
        -- but if the code still raises or returns a non-bool value
        against a real locus (e.g. a data shape the dry run's test locus
        didn't cover), the whole consumer stops rather than silently
        skipping that locus and continuing. The failure is recorded on
        the subscription (see `_record_handler_warning`, shown on the
        ingestion page) before the consumer stops, including the handler
        source itself so the operator can see exactly what needs fixing
        without checking server logs.
    save_all_targets : bool, optional
        If `True`, every locus that passes the handler filter (or every
        locus, if no handler is set) is saved as a GOATS `Target` -- once
        per locus, checked via `locus_is_saved_as_target` before saving,
        since the same locus can receive many alerts and we don't want to
        re-save (or error trying to) on every single one. A save failure
        is logged and does not stop ingestion of that locus into
        `AntaresLocus`, nor the consumer as a whole -- unlike a handler
        failure, a save failure doesn't indicate the handler itself is
        broken, so there's no reason to stop processing other loci over
        it.
    group : str, optional
        Kafka consumer group name, set on the ingestion page. Falls back
        to `DEFAULT_GROUP` if not given or blank. See
        `goats_tom.models.AntaresStreamSubscription.group`.
    generation : int, optional
        Fencing token: the subscription's generation number at the time
        this consumer was started (see
        `goats_tom.antares_stream_control._advance_generation`). Checked
        before every write; if the subscription's *current* generation
        has moved past this value (because a newer restart/stop
        happened), this consumer stops immediately without writing,
        guaranteeing it can never clash with a newer consumer even if its
        `abort()` signal was delayed or lost.

    Raises
    ------
    ValueError
        If `topics` is empty, or no ANTARES Kafka credentials are stored
        (see `_get_streaming_config`).
    LocusHandlerError
        If `handler_code` raises or returns a non-bool value against a
        real locus from the stream. Stops the consumer (see above).
    """
    from antares_client import StreamingClient  # noqa: PLC0415
    from dramatiq_abort import Abort  # noqa: PLC0415

    _apply_antares_api_timeout()

    if handler_code and is_effectively_blank(handler_code):
        logger.info(
            "handler_code is effectively blank (comments/whitespace "
            "only); treating as no handler."
        )
        handler_code = None

    try:
        config = _get_streaming_config(topics, group=group)
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
        _record_handler_warning(f"Consumer failed to start: {exc}")
        _mark_not_running()
        raise

    logger.info("ANTARES Kafka consumer started for topics: %s", config["topics"])
    _mark_running()
    _clear_stale_handler_warning()

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
                if not _is_current_generation(generation):
                    logger.info(
                        "Generation %d superseded; stopping consumer for "
                        "topics=%s.",
                        generation,
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
                            f"No messages received on topics={topics} "
                            f"within {STARTUP_SILENCE_WARNING_SECONDS} "
                            f"seconds of starting. This can mean the "
                            f"credentials are being silently rejected by "
                            f"ANTARES (a known limitation: the underlying "
                            f"Kafka client does not report invalid "
                            f"credentials as an error), or simply that "
                            f"the topic(s) have had no new alerts yet. "
                            f"Still running -- not stopped automatically, "
                            f"since a quiet topic is a legitimate "
                            f"possibility this can't be distinguished "
                            f"from. If you're confident the topic should "
                            f"be active, double-check your credentials."
                        )
                        warned_about_silence = True
                    continue

                received_first_message = True
                if warned_about_silence:
                    # Real data arrived after all -- clear the warning
                    # rather than leave a stale "might be broken" message
                    # once we have direct evidence it's actually working.
                    _clear_stale_handler_warning()
                    warned_about_silence = False

                if handler_code:
                    try:
                        keep = run_locus_handler(handler_code, locus)
                    except LocusHandlerError as exc:
                        logger.error(
                            "User-defined locus handler failed for locus_id=%s; "
                            "stopping the consumer.",
                            getattr(locus, "locus_id", None),
                        )
                        _record_handler_warning(
                            f"{exc}\n\nHandler code:\n{handler_code}"
                        )
                        _mark_not_running()
                        raise
                    if not keep:
                        continue

                try:
                    _upsert_locus(locus)

                    if save_all_targets and not locus_is_saved_as_target(
                        locus.locus_id
                    ):
                        try:
                            save_locus_as_target(locus.locus_id)
                        except SaveLocusError:
                            logger.exception(
                                "Auto-save failed for locus_id=%s; ingestion "
                                "continues.",
                                locus.locus_id,
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
        _record_handler_warning(f"Consumer failed unexpectedly: {exc}")
        _mark_not_running()
        raise

    logger.info("ANTARES Kafka consumer stopped.")
