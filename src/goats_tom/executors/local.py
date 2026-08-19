"""Executor that runs stream consumption on the GOATS host, as today."""

__all__ = ["LocalExecutor"]

import logging
from typing import Any

from dramatiq_abort import abort

from .base import ExecutorHandle, StreamExecutor

logger = logging.getLogger(__name__)


class LocalExecutor(StreamExecutor):
    """Wraps today's Dramatiq path with no behaviour change.

    Notes
    -----
    This is a transcription of what `antares_stream_control` already did
    inline, not a reimplementation. `is_running` is still set by the actor
    itself rather than here: `.send()` only enqueues, so setting it at start
    would be optimistic rather than confirmed.

    The actor is imported inside `start` rather than at module scope. It
    pulls in Django models transitively, so a top-level import would make
    ``import goats_tom.executors`` require a configured settings module and
    a populated app registry -- turning a cheap import into one that is
    order-dependent at start-up and awkward to exercise in tests.
    """

    name = "local"

    def start(self, subscription, generation: int) -> ExecutorHandle:
        """Enqueue the ingest actor for `subscription`."""
        from goats_tom.tasks.ingest_antares_stream import (  # noqa: PLC0415
            ingest_antares_stream,
        )

        message = ingest_antares_stream.send(
            subscription_id=subscription.pk,
            generation=generation,
        )
        return ExecutorHandle(kind=self.name, message_id=message.message_id)

    def stop(self, subscription) -> None:
        """Abort the tracked consumer, if any."""
        if not (subscription.dramatiq_message_id and subscription.is_running):
            return
        logger.info(
            "Aborting ANTARES stream consumer (message_id=%s).",
            subscription.dramatiq_message_id,
        )
        try:
            abort(subscription.dramatiq_message_id)
        except Exception:
            # Best-effort: the message may have already finished or the
            # broker restarted. The generation fencing token still protects
            # correctness if this silently fails.
            logger.exception(
                "Failed to abort ANTARES stream consumer (message_id=%s).",
                subscription.dramatiq_message_id,
            )

    def status(self, subscription) -> dict[str, Any]:
        """Report running state from the subscription row."""
        return {
            "running": bool(subscription.is_running),
            "message_id": subscription.dramatiq_message_id,
        }
