"""Helper for (re)starting and stopping the ANTARES Kafka stream consumer.

Used by the "Ingest from Kafka stream" form (see
`goats_tom.views.antares_stream_subscribe`) to swap the running consumer's
topic list, or stop it entirely, without editing `local_settings.py` or
restarting the whole `goats run` process.
"""

__all__ = ["restart_antares_stream", "stop_antares_stream", "advance_generation"]

import logging

from django.db.models import F
from dramatiq_abort import abort

from goats_tom.models import AntaresStreamSubscription
from goats_tom.tasks import ingest_antares_stream

logger = logging.getLogger(__name__)


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
