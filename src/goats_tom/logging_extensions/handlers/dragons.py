"""Class for sending logs over WebSocket for DRAGONS logs."""

__all__ = ["DRAGONSHandler"]

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class DRAGONSHandler(logging.Handler):
    """A custom logging handler that sends messages to a WebSocket consumer group for
    DRAGONS logs.
    """

    group_name = "dragons_group"
    func_type = "log.message"

    def __init__(self, recipe_id: int, reduce_id: int, run_id: int) -> None:
        """Initialize the handler with the channel layer."""
        super().__init__()
        self.recipe_id = recipe_id
        self.reduce_id = reduce_id
        self.run_id = run_id
        self.channel_layer = get_channel_layer()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record. The log message is sent to the WebSocket group.

        Parameters
        ----------
        record : `logging.LogRecord`
            The log record to process.

        """
        log_entry = self.format(record)

        # Send message to the group.
        try:
            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
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
