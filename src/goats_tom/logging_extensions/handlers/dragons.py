"""Class for sending logs over WebSocket for DRAGONS logs."""

__all__ = ["DRAGONSHandler"]

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from goats_tom.context.user_context import get_current_user_id
from goats_tom.realtime.groups import DRAGONS_PREFIX, user_group


class DRAGONSHandler(logging.Handler):
    """A custom logging handler that sends messages to a WebSocket consumer group for
    DRAGONS logs.

    The reduction this handler speaks for is fixed when it is built, the user
    included: it is attached to a logger DRAGONS shares, so a record it is
    handed may well have been emitted by another reduction's thread.
    """

    func_type = "log.message"

    def __init__(self, recipe_id: int, reduce_id: int, run_id: int) -> None:
        """Initialize the handler with the channel layer."""
        super().__init__()
        self.recipe_id = recipe_id
        self.reduce_id = reduce_id
        self.run_id = run_id
        self.group = user_group(DRAGONS_PREFIX, get_current_user_id())
        self.channel_layer = get_channel_layer()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record. The log message is sent to the WebSocket group.

        Parameters
        ----------
        record : `logging.LogRecord`
            The log record to process.

        """
        if self.group is None:
            # Dropped rather than broadcast: a reduction log names files and
            # runs, and is nobody's business but its owner's.
            return

        log_entry = self.format(record)

        # Send message to the group.
        try:
            async_to_sync(self.channel_layer.group_send)(
                self.group,
                {
                    "type": self.func_type,
                    "message": log_entry,
                    "recipe_id": self.recipe_id,
                    "reduce_id": self.reduce_id,
                    "run_id": self.run_id,
                },
            )
        except Exception:
            # Use logging.Handler builtin error handling.
            self.handleError(record)
