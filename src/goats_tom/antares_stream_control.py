"""Helper for (re)starting and stopping the ANTARES Kafka stream consumer.

Used by the "Ingest from Kafka stream" form (see
`goats_tom.views.antares_stream_subscribe`) to swap the running consumer's
topic list, or stop it entirely, without editing `local_settings.py` or
restarting the whole `goats run` process.
"""

__all__ = [
    "restart_antares_stream",
    "stop_antares_stream",
    "advance_generation",
    "fetch_available_topics",
]

import datetime
import logging

from django.db.models import F
from django.utils import timezone
from dramatiq_abort import abort

from goats_tom.models import AntaresStreamSubscription
from goats_tom.tasks import ingest_antares_stream
from goats_tom.tasks.ingest_antares_stream import get_antares_kafka_login

logger = logging.getLogger(__name__)

# How long to wait for the Kafka broker's topic-listing admin request
# before giving up. This is a single, direct request/response (unlike the
# consumer's own long-lived polling loop), so a short timeout is
# appropriate -- a slow/unreachable broker should fail fast here rather
# than hang the "Ingest from Kafka stream" page.
TOPIC_LIST_TIMEOUT_SECONDS = 10

# antares_client.stream.StreamingClient prefixes every topic with this
# string before subscribing (see antares_client's own
# StreamingClient._TOPIC_PREFIX) -- topics on the broker are named e.g.
# "client.young-rubin-transients", but users type/select just
# "young-rubin-transients" (matching what StreamingClient itself expects
# as input). Confirmed by reading antares_client's source directly.
ANTARES_TOPIC_PREFIX = "client."

# A topic is considered "active" (shown in the ingestion form's dropdown)
# if its most recent message is within this many days. There is no
# Kafka-level "last message time" field on topic metadata itself -- this
# requires actually fetching each topic's single most recent message and
# checking its timestamp (see _topic_has_recent_message), one broker
# round-trip per topic. Deliberately not cached (see the calling view):
# only checked when the user actually opens the dropdown, not on every
# page load, so the added latency is an accepted, on-demand cost, not one
# that compounds across every page view.
ACTIVE_TOPIC_MAX_AGE_DAYS = 30

# How long to wait for the single batched offsets_for_times() call that
# checks every candidate topic's activity at once (see
# _find_active_topics). Longer than a typical single-topic request would
# need, since this one call now covers every partition of every candidate
# topic together -- if it times out, every topic is excluded (see
# _find_active_topics' except branch), not just one, so it's worth
# giving it more room than the old per-topic design did.
ACTIVE_TOPIC_CHECK_TIMEOUT_SECONDS = 15


class TopicListError(Exception):
    """Raised when the available topic list can't be fetched."""


def _find_active_topics(
    consumer, candidate_names: list[str], topic_partitions: dict, max_age_days: int
) -> set[str]:
    """Check which of `candidate_names` have a message newer than
    `max_age_days`, in one batched broker call.

    Parameters
    ----------
    consumer : `confluent_kafka.Consumer`
        An already-connected consumer to query with.
    candidate_names : list of str
        Full (prefixed) topic names to check.
    topic_partitions : dict
        Maps each name in `candidate_names` to its partition IDs (from
        `ClusterMetadata.topics[name].partitions`).
    max_age_days : int
        How many days back counts as "recent".

    Returns
    -------
    set of str
        The subset of `candidate_names` with at least one partition whose
        latest message is newer than `max_age_days` ago. Topics with no
        partitions, or where the check fails entirely, are excluded
        rather than included by default -- the point is to hide topics
        that might be inactive or unreachable.

    Notes
    -----
    Kafka has no "last message time" field on topic metadata itself, but
    `Consumer.offsets_for_times()` answers a closely related, sufficient
    question directly, server-side, for many partitions across many
    topics in a single call: "what is the earliest offset at or after
    this timestamp, for each of these partitions". If a partition's
    latest message is older than the cutoff, the given timestamp exceeds
    every message in it, and the broker returns `offset == -1` for that
    partition (per `offsets_for_times`' own documented behavior) --
    checking `offset != -1` is therefore exactly "this partition has a
    message at or after the cutoff", with no need to separately fetch or
    inspect any actual message. This replaced an earlier, working but
    much less efficient per-topic implementation (`assign()` + `poll()`
    for each topic's single latest message, checking its real
    timestamp) -- functionally equivalent, but this needs roughly one
    broker round-trip total instead of up to two per topic.
    """
    from confluent_kafka import TopicPartition  # noqa: PLC0415

    cutoff = timezone.now() - datetime.timedelta(days=max_age_days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    query_partitions = [
        TopicPartition(name, partition_id, cutoff_ms)
        for name in candidate_names
        for partition_id in topic_partitions.get(name, {})
    ]
    if not query_partitions:
        return set()

    try:
        results = consumer.offsets_for_times(
            query_partitions, timeout=ACTIVE_TOPIC_CHECK_TIMEOUT_SECONDS
        )
    except Exception:
        logger.exception(
            "Failed to check topic activity via offsets_for_times; "
            "excluding all candidate topics from the dropdown."
        )
        return set()

    active = set()
    for tp in results:
        if tp.offset is not None and tp.offset >= 0:
            active.add(tp.topic)
    return active


def fetch_available_topics() -> list[str]:
    """List ANTARES Kafka topics available to the stored credentials,
    filtered to only "active" ones.

    Used by the "Ingest from Kafka stream" form to offer a dropdown of
    real, currently-active topic names instead of requiring free-text
    entry, and instead of showing every topic ever created regardless of
    whether it's still receiving alerts.

    Returns
    -------
    list of str
        Active topic names, with ANTARES's internal "client." prefix
        stripped (so they match what `StreamingClient`/the ingestion form
        itself expects -- see `ANTARES_TOPIC_PREFIX`), sorted
        alphabetically. Topics without that prefix (any other topics the
        broker happens to expose that aren't ANTARES's own client-facing
        streams) are excluded, since they wouldn't be valid input to the
        form anyway. A topic only appears here if it has a message newer
        than `ACTIVE_TOPIC_MAX_AGE_DAYS` (see `_topic_has_recent_message`)
        -- topics that are empty, too old, or fail the activity check for
        any reason are silently excluded rather than shown.

    Raises
    ------
    TopicListError
        If no superuser has stored ANTARES Kafka credentials, or the
        broker request fails (network issue, invalid credentials, etc.).

    Notes
    -----
    `antares_client.StreamingClient` has no built-in way to list
    available topics -- its own `topics` property just echoes back
    whatever topics were passed into its constructor (confirmed by
    reading its source), and there is no dedicated listing endpoint
    anywhere in the `antares_client` package.

    Two earlier approaches were tried and ruled out, both confirmed by
    directly testing against the real broker, not guessed:

    1. Constructing `StreamingClient` with an empty topic list, purely to
       reuse its internal `Consumer` for `.list_topics()`. Rejected:
       `StreamingClient.__init__` unconditionally calls
       `self._consumer.subscribe([])`, which `librdkafka` rejects
       (`KafkaError._INVALID_ARG`: "Failed to set subscription: Invalid
       argument or configuration").
    2. `confluent_kafka.admin.AdminClient.list_topics()`, built with the
       same connection config `StreamingClient` itself constructs
       internally. Rejected: `AdminClient` opens its connection in a
       different broker-facing role (`librdkafka` logs show it as
       `rdkafka#producer-1`, not a consumer), and ANTARES's broker
       rejected that role's SASL authentication outright (`Broker
       transport failure` / `SaslAuthenticateRequest failed`) even with
       valid credentials -- apparently these credentials are scoped for
       consuming, not admin/producer operations.

    This third approach avoids both problems: it constructs a real,
    fully valid `StreamingClient` -- the exact same object, connection
    role, and code path already proven to work for actual ingestion
    throughout this project -- subscribed via a regex topic pattern
    (`confluent_kafka.Consumer.subscribe()` supports `"^pattern"`
    subscriptions) matching every ANTARES client-facing topic, rather
    than an empty list or a guessed specific topic name. `.list_topics()`
    is then called on that real `Consumer` (accessible as the
    `StreamingClient` instance's own `_consumer` attribute), which is the
    same consumer role/credentials scope that already works.

    Reaching into `StreamingClient._consumer` (a single-underscore,
    conventionally-private attribute) is a real coupling to
    `antares_client`'s internal implementation, not its public API --
    `StreamingClient` has no public method that exposes `.list_topics()`
    itself. If a future `antares_client` release renames or restructures
    this attribute, this function would need updating. Accepted as a
    reasonable tradeoff given `antares_client` has no supported way to do
    this at all, and this is the only approach (of three tried) that
    actually works against ANTARES's real broker permissions.
    """
    from antares_client.stream import StreamingClient  # noqa: PLC0415

    login = get_antares_kafka_login()
    if login is None:
        raise TopicListError(
            "No ANTARES Kafka credentials found. A superuser must store "
            "them via the Credential Manager (Users -> Manage -> ANTARES "
            "Kafka Stream) first."
        )

    try:
        # A regex-pattern subscription ("^" prefix, per confluent_kafka's
        # Consumer.subscribe() docs) matching every ANTARES client-facing
        # topic -- a real, valid, non-empty subscription that doesn't
        # require guessing any specific topic name in advance.
        pattern = "^" + ANTARES_TOPIC_PREFIX.replace(".", r"\.") + ".*"
        client = StreamingClient(
            topics=[pattern],
            api_key=login.api_key,
            api_secret=login.api_secret,
        )
    except Exception as exc:
        raise TopicListError(
            f"Failed to connect to the ANTARES Kafka broker: {exc}"
        ) from exc

    try:
        cluster_metadata = client._consumer.list_topics(
            timeout=TOPIC_LIST_TIMEOUT_SECONDS
        )

        candidate_names = sorted(
            name
            for name in cluster_metadata.topics
            if name.startswith(ANTARES_TOPIC_PREFIX)
        )
        topic_partitions = {
            name: cluster_metadata.topics[name].partitions for name in candidate_names
        }

        # Only topics with a message in the last ACTIVE_TOPIC_MAX_AGE_DAYS
        # days are shown -- checked in one batched broker call across
        # every partition of every candidate topic (see
        # _find_active_topics), not triggered on every page load, only
        # when the dropdown is actually opened. Reuses this same
        # `client._consumer` (already in subscribe() mode from
        # StreamingClient's own __init__) rather than a separate
        # dedicated consumer: `offsets_for_times()` is a pure metadata
        # query, not partition assignment, so -- unlike `assign()`, which
        # is genuinely incompatible with an active subscribe() on the
        # same consumer -- it doesn't conflict. Confirmed directly (not
        # assumed): calling it on a subscribed consumer against an
        # unreachable test broker fails with `_ALL_BROKERS_DOWN` (a plain
        # network error), not a local mode-conflict rejection, meaning
        # the call itself is accepted and would proceed normally against
        # a real, reachable broker.
        active_topic_names = _find_active_topics(
            client._consumer,
            candidate_names,
            topic_partitions,
            ACTIVE_TOPIC_MAX_AGE_DAYS,
        )
    except Exception as exc:
        raise TopicListError(
            f"Failed to list topics from the ANTARES Kafka broker: {exc}"
        ) from exc
    finally:
        client.close()

    topics = sorted(
        name[len(ANTARES_TOPIC_PREFIX) :] for name in active_topic_names
    )
    return topics


def _get_or_create_subscription() -> AntaresStreamSubscription:
    """Fetch the current subscription row, creating one if none exists yet.

    Returns
    -------
    `AntaresStreamSubscription`
        The current (most recently updated) subscription row.
    """
    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is None:
        subscription = AntaresStreamSubscription.objects.create()
    return subscription


def advance_generation(subscription: AntaresStreamSubscription) -> int:
    """Atomically increment `generation` and return the new value.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        The row whose generation to advance.

    Returns
    -------
    int
        The new generation number.

    Notes
    -----
    This is the actual correctness guarantee against consumer clashes (see
    `ingest_antares_stream`'s fencing-token check before every write): any
    consumer started with an older generation number will see, on its next
    write attempt, that the subscription's *current* generation has moved
    past its own and stop -- regardless of whether its `abort()` signal
    was ever received or acted on. Uses `F("generation") + 1` for an
    atomic database-level increment rather than read-then-write in Python,
    so two near-simultaneous restart requests can't both compute the same
    "next" generation number from a stale read.
    """
    AntaresStreamSubscription.objects.filter(pk=subscription.pk).update(
        generation=F("generation") + 1
    )
    subscription.refresh_from_db(fields=["generation"])
    return subscription.generation


def _abort_running_consumer(subscription: AntaresStreamSubscription) -> None:
    """Best-effort abort of the consumer tracked by `subscription`, if any.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        Row whose `dramatiq_message_id` identifies the running consumer to
        abort, if `is_running` is set.

    Notes
    -----
    This is purely an optimization -- stop the old consumer from doing
    more wasted work as soon as possible -- not the mechanism that
    prevents it from writing stale data. That guarantee comes from the
    generation fencing token (see `advance_generation` and
    `ingest_antares_stream`), which the old consumer will observe on its
    very next write attempt regardless of whether this abort signal is
    ever received or acted on. `dramatiq_abort` can't interrupt a
    blocking C-level Kafka call and provides no way to confirm a specific
    message has actually stopped, which is exactly why a fixed delay was
    not a real guarantee and the fencing token is used instead.
    """
    if not (subscription.dramatiq_message_id and subscription.is_running):
        return

    logger.info(
        "Aborting ANTARES stream consumer (message_id=%s).",
        subscription.dramatiq_message_id,
    )
    try:
        abort(subscription.dramatiq_message_id)
    except Exception:
        # Best-effort: if the message can't be found/aborted (e.g. it
        # already finished, or the broker restarted), log and move on --
        # the generation fencing token still protects correctness even if
        # this abort silently fails.
        logger.exception(
            "Failed to abort ANTARES stream consumer (message_id=%s).",
            subscription.dramatiq_message_id,
        )


def restart_antares_stream(
    topics: list[str],
    group: str = "",
    save_all_targets: bool = False,
    trigger_gemini_observations: bool = False,
    handler_code: str = "",
) -> AntaresStreamSubscription:
    """Abort the currently-running ANTARES consumer, if any, and start a
    new one with the given topics -- guaranteed not to clash with the old
    one via a generation fencing token, not just a best-effort abort.

    Parameters
    ----------
    topics : list of str
        Kafka topics to subscribe to.
    group : str, optional
        Kafka consumer group name. Falls back to a built-in default if
        blank (see `goats_tom.tasks.ingest_antares_stream.DEFAULT_GROUP`).
    save_all_targets : bool, optional
        If `True`, every locus ingested while this subscription is active
        is saved as a GOATS `Target` (see
        `goats_tom.tasks.ingest_antares_stream` and
        `goats_tom.antares_target_save`).
    trigger_gemini_observations : bool, optional
        Stored on the subscription row for future use. Currently a no-op
        (default `False`).
    handler_code : str, optional
        User-defined locus filter/handler function body, passed through to
        the consumer. See `goats_tom.antares_locus_handler`.

    Returns
    -------
    `AntaresStreamSubscription`
        The updated subscription row, reflecting the new topics, group,
        generation, and the new consumer's Dramatiq message ID.

    Notes
    -----
    Correctness against clashing with the old consumer comes from a
    generation fencing token, not from waiting for `abort()` to take
    effect: this function advances `subscription.generation` *before*
    starting the new consumer, and passes that new generation to it. The
    old consumer (started with the previous generation) checks, before
    every write, whether the subscription's *current* generation in the
    database still matches the generation it was started with -- if not,
    it stops immediately rather than writing. This holds even if the old
    consumer's `abort()` signal is delayed, lost, or can't interrupt a
    blocking Kafka call: the next time it tries to write anything, it
    will see it's been superseded and stop. `abort()` is still sent, as
    an optimization to stop the old consumer's wasted work sooner, but is
    no longer what correctness depends on.

    `is_running` is set by the actor itself (see
    `goats_tom.tasks.ingest_antares_stream._mark_running`/
    `_mark_not_running`), not here -- `.send()` only enqueues the actor,
    which may not run until sometime after this function (and the web
    request that called it) returns, so setting it here would be
    optimistic rather than confirmed.
    """
    subscription = _get_or_create_subscription()

    _abort_running_consumer(subscription)

    new_generation = advance_generation(subscription)

    message = ingest_antares_stream.send(
        topics=topics,
        handler_code=handler_code,
        save_all_targets=save_all_targets,
        group=group,
        generation=new_generation,
    )

    subscription.topics = topics
    subscription.group = group
    subscription.save_all_targets = save_all_targets
    subscription.trigger_gemini_observations = trigger_gemini_observations
    subscription.handler_code = handler_code
    subscription.dramatiq_message_id = message.message_id
    # Deliberately NOT setting is_running = True here. `.send()` only
    # enqueues the actor; it may not actually run for some time after
    # this web request (and its redirect) complete. Setting is_running
    # optimistically here created a race: if the actor then failed to
    # start (e.g. missing credentials), the page could show "Running"
    # right alongside the very error explaining why it wasn't. The actor
    # itself now sets is_running = True (see
    # goats_tom.tasks.ingest_antares_stream._mark_running) once it has
    # genuinely confirmed startup, so this field only ever reflects
    # confirmed state -- briefly showing "Stopped" right after submission
    # is more honest than showing a "Running" that might not be true yet.
    subscription.save()

    logger.info(
        "Started ANTARES stream consumer for topics=%s group=%r "
        "generation=%d (message_id=%s).",
        topics,
        group,
        new_generation,
        message.message_id,
    )
    return subscription


def stop_antares_stream() -> AntaresStreamSubscription | None:
    """Abort the currently-running ANTARES consumer without starting a new one.

    Returns
    -------
    `AntaresStreamSubscription` or None
        The updated subscription row (marked not running), or `None` if
        there was no subscription row to update.

    Notes
    -----
    Also advances `generation` (see `restart_antares_stream`'s docstring
    for why this is the real correctness guarantee, not the `abort()`
    call): this guarantees the stopped consumer stops writing on its next
    write attempt even if the abort signal is delayed, lost, or can't
    interrupt a blocking Kafka call.
    """
    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is None:
        return None

    _abort_running_consumer(subscription)
    advance_generation(subscription)

    subscription.is_running = False
    subscription.dramatiq_message_id = None
    subscription.save()

    logger.info("Stopped ANTARES stream consumer.")
    return subscription
