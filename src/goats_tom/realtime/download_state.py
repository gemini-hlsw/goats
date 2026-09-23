"""Class that stores and sends the current state of a download task."""

__all__ = ["DownloadState"]

import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from goats_tom.context.user_context import get_current_user_id

from .groups import UPDATES_PREFIX, user_group

logger = logging.getLogger(__name__)


class DownloadState:
    """Class responsible for managing the state of the download task.

    Updates reach only the user whose download they describe, resolved from the
    task context.
    """

    func_type = "download.message"

    def __init__(self) -> None:
        self.unique_id: str = f"{uuid.uuid4()}"
        self.label: str = ""
        self.status: str = ""
        self.downloaded_bytes: int | None = None
        self.message: str = ""
        self.done: bool = False
        self.error: bool = False

    def update_and_send(
        self,
        label: str | None = None,
        status: str | None = None,
        downloaded_bytes: int | None = None,
        message: str | None = None,
        done: bool | None = None,
        error: bool | None = None,
    ) -> None:
        """Updates part or all of the current state of the download and then
        sends.

        Parameters
        ----------
        label : `str | None`, optional
            The label to display, by default `None`.
        status : `str | None`, optional
            The current status, by default `None`.
        downloaded_bytes : `int | None`, optional
            Total amount of bytes downloaded so far, by default `None`.
        message : `str | None`, optional
            Message describing in detail extra details, by default `None`.
        done : `bool | None`, optional
            Whether the download task is done or not, by default `None`.
        error : `bool | None`, optional
            Whether there was an error in the task, by default `None`.

        """
        if label is not None:
            self.label = label
        if status is not None:
            self.status = status
        if downloaded_bytes is not None:
            self.downloaded_bytes = downloaded_bytes
        if message is not None:
            self.message = message
        if done is not None:
            self.done = done
        if error is not None:
            self.error = error

        self._send()

    def _send(self) -> None:
        """Sends a download update over the websocket."""
        group = user_group(UPDATES_PREFIX, get_current_user_id())
        if group is None:
            # Dropped rather than broadcast: better lost than shown to all.
            logger.warning(
                "Dropping download update %r: no user to address it to.", self.label
            )
            return

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": self.func_type,
                "label": self.label,
                "message": self.message,
                "status": self.status,
                "downloaded_bytes": self.format_bytes(self.downloaded_bytes),
                "unique_id": self.unique_id,
                "done": self.done,
                "error": self.error,
            },
        )

    @staticmethod
    def format_bytes(downloaded_bytes: int | None = None) -> str:
        """Converts the number of bytes into a more readable format, choosing the
        appropriate unit from bytes, kilobytes (KB), megabytes (MB),
        gigabytes (GB), or terabytes (TB), with a specific number of decimal
        places for each unit.

        Parameters
        ----------
        downloaded_bytes : `int | None`, optional
            The total amount of data in bytes.

        Returns
        -------
        `str`
            A string representation of the data size.

        """
        if downloaded_bytes is None:
            return ""

        # Define thresholds and formatting rules for each unit
        if downloaded_bytes < 1024:  # Bytes
            return f"{downloaded_bytes} B"
        elif downloaded_bytes < 1024**2:  # Kilobytes
            return f"{downloaded_bytes / 1024:.0f} KB"
        elif downloaded_bytes < 1024**3:  # Megabytes
            return f"{downloaded_bytes / 1024**2:.1f} MB"
        elif downloaded_bytes < 1024**4:  # Gigabytes
            return f"{downloaded_bytes / 1024**3:.2f} GB"
        else:  # Terabytes and beyond
            return f"{downloaded_bytes / 1024**4:.3f} TB"
