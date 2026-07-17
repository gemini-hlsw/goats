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

This actor is intended to run inside the existing `rundramatiq` worker
process that GOATS already starts via `goats run` -- no new process type is
introduced. It runs `while True` via `StreamingClient.iter()`, so it occupies
one Dramatiq worker thread/process for the lifetime of the app.
"""

__all__ = ["ingest_antares_stream"]

import logging

import dramatiq
from django.db import transaction

from goats_tom.antares_locus_handler import LocusHandlerError, run_locus_handler
from goats_tom.antares_target_save import (
    SaveLocusError,
    locus_is_saved_as_target,
    save_locus_as_target,
)
from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

DEFAULT_GROUP = "goats-antares-locus-dashboard"


def _get_streaming_config(topics: list[str]) -> dict:
    """Build the `StreamingClient` kwargs from an explicit topic list and
    stored ANTARES Kafka credentials.

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
        "group": login.group or DEFAULT_GROUP,
    }


def _record_handler_warning(message: str) -> None:
    """Save a handler-code warning to the current subscription row, so it
    shows up on the ingestion page without needing to check server logs.

    Parameters
    ----------
    message : str
        The warning/error message to display.

    Notes
    -----
    Updates the most recently-updated `AntaresStreamSubscription` row --
    same "current subscription" lookup used throughout this feature (see
    `goats_tom.antares_stream_control`), since only one subscription is
    meant to be active at a time.
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


def _clear_handler_warning() -> None:
    """Clear any previously-recorded handler warning, if one is set.

    Only writes to the database if there's actually something to clear
    (checked first), since this runs on every successful handler call --
    a write on every single message, even when there's nothing to change,
    would be wasteful.
    """
    from goats_tom.models import AntaresStreamSubscription  # noqa: PLC0415

    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is not None and subscription.last_handler_warning:
        subscription.last_handler_warning = ""
        subscription.last_handler_warning_at = None
        subscription.save(
            update_fields=["last_handler_warning", "last_handler_warning_at"]
        )


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
        row, created = AntaresLocus.objects.select_for_update().get_or_create(
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
        `goats_tom.antares_locus_handler.run_locus_handler`. If the code
        raises, that locus is logged and skipped (not the whole consumer)
        so one bad handler invocation doesn't kill ingestion entirely.
    save_all_targets : bool, optional
        If `True`, every locus that passes the handler filter (or every
        locus, if no handler is set) is saved as a GOATS `Target` -- once
        per locus, checked via `locus_is_saved_as_target` before saving,
        since the same locus can receive many alerts and we don't want to
        re-save (or error trying to) on every single one. A save failure
        is logged and does not stop ingestion of that locus into
        `AntaresLocus`, nor the consumer as a whole.

    Raises
    ------
    ValueError
        If `topics` is empty, or no ANTARES Kafka credentials are stored
        (see `_get_streaming_config`).
    """
    from antares_client import StreamingClient  # noqa: PLC0415

    config = _get_streaming_config(topics)
    logger.info("ANTARES Kafka consumer started for topics: %s", config["topics"])

    with StreamingClient(
        config["topics"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        group=config["group"],
    ) as client:
        for topic, locus in client.iter():
            try:
                if handler_code:
                    try:
                        keep = run_locus_handler(handler_code, locus)
                        _clear_handler_warning()
                    except LocusHandlerError as exc:
                        logger.exception(
                            "User-defined locus handler failed for "
                            "locus_id=%s; keeping locus by default.",
                            getattr(locus, "locus_id", None),
                        )
                        _record_handler_warning(str(exc))
                        keep = True
                    if not keep:
                        continue
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
                    "Failed to process ANTARES locus update: topic=%s locus_id=%s",
                    topic,
                    getattr(locus, "locus_id", None),
                )

    logger.info("ANTARES Kafka consumer stopped.")
