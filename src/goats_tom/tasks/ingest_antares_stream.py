"""
Long-running Dramatiq actor that consumes the ANTARES Kafka alert stream and
maintains the `AntaresLocus` staging table used by the live alert dashboard.

Uses `antares_client.StreamingClient`, which handles the Kafka connection,
SASL auth, and Avro decoding internally and yields `(topic, Locus)` tuples --
so this module only has to translate a `Locus` into a staging-table row.

Requires Django settings:

    ANTARES_KAFKA_API_KEY = "..."
    ANTARES_KAFKA_API_SECRET = "..."
    ANTARES_KAFKA_TOPICS = ["<your_alert_stream_topic>"]

Optional:

    ANTARES_KAFKA_GROUP = "goats-antares-locus-dashboard"  # Kafka consumer
        # group name. Defaults to DEFAULT_GROUP below if unset. Set this
        # explicitly (rather than relying on antares_client's own default,
        # which falls back to the machine's hostname) so the consumer
        # group -- and therefore offset tracking -- stays stable across
        # restarts and across different hosts/containers.

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
from django.conf import settings
from django.db import transaction

from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

DEFAULT_GROUP = "goats-antares-locus-dashboard"


def _get_streaming_config() -> dict:
    """Build the `StreamingClient` kwargs from Django settings.

    Returns
    -------
    dict
        Keyword arguments for `antares_client.StreamingClient`.

    Raises
    ------
    ValueError
        If required ANTARES Kafka streaming settings are missing.
    """
    topics = list(getattr(settings, "ANTARES_KAFKA_TOPICS", []))
    api_key = getattr(settings, "ANTARES_KAFKA_API_KEY", None)
    api_secret = getattr(settings, "ANTARES_KAFKA_API_SECRET", None)
    group = getattr(settings, "ANTARES_KAFKA_GROUP", DEFAULT_GROUP)

    if not topics:
        raise ValueError("ANTARES_KAFKA_TOPICS must list at least one topic.")
    if not api_key or not api_secret:
        raise ValueError(
            "ANTARES_KAFKA_API_KEY and ANTARES_KAFKA_API_SECRET must both be "
            "set to ingest the ANTARES Kafka stream."
        )

    return {
        "topics": topics,
        "api_key": api_key,
        "api_secret": api_secret,
        "group": group,
    }


def _upsert_locus(locus) -> None:
    """Create or update the `AntaresLocus` staging row for one locus update.

    Parameters
    ----------
    locus : `antares_client.models.Locus`
        The locus received from the stream.

    Notes
    -----
    `locus.properties`, by contrast, IS always populated on every locus
    update from the stream (it's not one of the lazy-loaded attributes).
    `properties["newest_alert_observation_time"]`, `properties["newest_alert_id"]`,
    `properties["num_alerts"]`, and `properties["newest_alert_magnitude"]`
    were all confirmed against a live stream payload or ANTARES' own docs,
    so those back `latest_alert_mjd`, `latest_alert_id`, `alert_count`, and
    `latest_alert_magnitude` respectively. `alert_count` uses ANTARES' own
    running total rather than a locally-incremented counter.

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
def ingest_antares_stream() -> None:
    """Continuously consume the ANTARES Kafka alert stream.

    Blocks indefinitely, receiving loci from `StreamingClient.iter()` and
    upserting rows into `AntaresLocus`. Enqueued once by
    `goats_scheduler.management.commands.run_scheduler` (not from
    `AppConfig.ready()`, which would fire in every process and enqueue
    duplicate consumers).

    `time_limit=float("inf")` disables Dramatiq's default 10-minute actor
    time limit. Without this, Dramatiq forcibly kills the worker thread
    after the default timeout, since this actor is designed to never
    return under normal operation.

    Raises
    ------
    ValueError
        If required Kafka streaming settings are missing (see
        `_get_streaming_config`).
    """
    from antares_client import StreamingClient  # noqa: PLC0415

    config = _get_streaming_config()
    logger.info("ANTARES Kafka consumer started for topics: %s", config["topics"])

    with StreamingClient(
        config["topics"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        group=config["group"],
    ) as client:
        for topic, locus in client.iter():
            try:
                _upsert_locus(locus)
            except Exception:
                logger.exception(
                    "Failed to process ANTARES locus update: topic=%s locus_id=%s",
                    topic,
                    getattr(locus, "locus_id", None),
                )

    logger.info("ANTARES Kafka consumer stopped.")
