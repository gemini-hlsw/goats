"""Helper for (re)starting and stopping the ANTARES Kafka stream consumer.

Used by the "Ingest from Kafka stream" form (see
`goats_tom.views.antares_stream_subscribe`) to swap the running consumer's
topic list, or stop it entirely, without editing `local_settings.py` or
restarting the whole `goats run` process.
"""

__all__ = ["restart_antares_stream", "stop_antares_stream"]

import logging

from dramatiq_abort import abort

from goats_tom.models import AntaresStreamSubscription
from goats_tom.tasks import ingest_antares_stream

logger = logging.getLogger(__name__)


def _abort_running_consumer(subscription: AntaresStreamSubscription) -> None:
    """Best-effort abort of the consumer tracked by `subscription`, if any.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        Row whose `dramatiq_message_id` identifies the running consumer to
        abort, if `is_running` is set.

    Notes
    -----
    See `restart_antares_stream`'s docstring for the caveats around abort
    timing -- this is best-effort and does not wait for the consumer to
    actually stop before returning.
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
        # already finished, or the broker restarted), log and move on
        # rather than blocking the user.
        logger.exception(
            "Failed to abort ANTARES stream consumer (message_id=%s).",
            subscription.dramatiq_message_id,
        )


def restart_antares_stream(
    topics: list[str],
    save_all_targets: bool = False,
    trigger_gemini_observations: bool = False,
    handler_code: str = "",
) -> AntaresStreamSubscription:
    """Abort the currently-running ANTARES consumer, if any, and start a
    new one with the given topics.

    Parameters
    ----------
    topics : list of str
        Kafka topics to subscribe to.
    save_all_targets : bool, optional
        Stored on the subscription row for future use. Currently a no-op
        (default `False`).
    trigger_gemini_observations : bool, optional
        Stored on the subscription row for future use. Currently a no-op
        (default `False`).
    handler_code : str, optional
        User-defined locus filter/handler function body, passed through to
        the consumer. See `goats_tom.antares_locus_handler`.

    Returns
    -------
    `AntaresStreamSubscription`
        The updated (or newly created) subscription row, reflecting the
        new topics and the new consumer's Dramatiq message ID.

    Notes
    -----
    Aborting is best-effort: `dramatiq_abort.abort()` signals the running
    worker thread to raise an exception at its next Python-level bytecode
    boundary (see the `Abortable` middleware docs). A consumer blocked
    inside `StreamingClient.iter()`'s underlying C/Kafka poll call may take
    a moment to actually stop after the abort signal is sent -- this
    function does not wait for that to happen before starting the new
    consumer, so there may be a brief window where two consumers are both
    connected under the same Kafka consumer group. This is expected to
    self-resolve (Kafka rebalances/dedupes within a group) and is not
    treated as an error here.
    """
    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is None:
        subscription = AntaresStreamSubscription()

    _abort_running_consumer(subscription)

    message = ingest_antares_stream.send(topics=topics, handler_code=handler_code)

    subscription.topics = topics
    subscription.save_all_targets = save_all_targets
    subscription.trigger_gemini_observations = trigger_gemini_observations
    subscription.handler_code = handler_code
    subscription.dramatiq_message_id = message.message_id
    subscription.is_running = True
    subscription.save()

    logger.info(
        "Started ANTARES stream consumer for topics=%s (message_id=%s).",
        topics,
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
    Same best-effort abort caveats as `restart_antares_stream` apply --
    see that function's docstring.
    """
    subscription = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    if subscription is None:
        return None

    _abort_running_consumer(subscription)

    subscription.is_running = False
    subscription.dramatiq_message_id = None
    subscription.save()

    logger.info("Stopped ANTARES stream consumer.")
    return subscription
