"""Class that updates and sends a notification."""

__all__ = ["NotificationInstance"]

import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class NotificationInstance:
    """Class responsible for creating and sending a notification."""

    group_name = "updates_group"
    func_type = "notification.message"

    @classmethod
    def create_and_send(
        cls,
        label: str = "",
        message: str = "",
        color: str = "primary",
    ) -> None:
        """Creates and sends a notification.

        Parameters
        ----------
        message : `str`, optional
            The body of the notification message to be sent, by default "".
        label : `str`, optional
            The label of the notification, by default "".
        color : `str`, optional
            The bootstrap color scheme to apply to the notification, by default
            "primary".

        """
        unique_id = f"{uuid.uuid4()}"
        cls._send(unique_id, label, message, color)

    @classmethod
    def _send(cls, unique_id: str, label: str, message: str, color: str) -> None:
        """Sends a notification.

        Parameters
        ----------
        unique_id: `str`
            The unique ID for the notification.
        message : `str`
            The body of the notification message to be sent.
        label : `str`
            The label of the notification.
        color : `str`
            The bootstrap color scheme to apply to the notification.

        """
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            cls.group_name,
            {
                "type": cls.func_type,
                "unique_id": unique_id,
                "label": label,
                "message": message,
                "color": color,
            },
        )
