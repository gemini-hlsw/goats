"""Class for updates through a websocket for all webpages."""

__all__ = ["UpdatesConsumer"]

import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class UpdatesConsumer(WebsocketConsumer):
    """A WebSocket consumer that handles sending updates to
    connected clients on all pages.

    Attributes
    ----------
    group_name : `str`
        The name of the group that this consumer handles updates for.

    """

    group_name = "updates_group"

    def connect(self) -> None:
        """Adds this consumer to the updates group upon WebSocket connection."""
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()

    def disconnect(self, code: int) -> None:
        """Removes this consumer from the updates group upon WebSocket disconnection.

        Parameters
        ----------
        code : `int`
            Return code to send on disconnect.

        """
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name, self.channel_name,
        )

    def notification_message(self, event: dict) -> None:
        """Sends a notification message to the client connected through WebSocket.

        Parameters
        ----------
        event : `dict`
            The event dictionary containing the notification data.

        """
        # Construct the notification message.
        notification = {
            "update": "notification",
            "unique_id": event["unique_id"],
            "color": event["color"],
            "label": event["label"],
            "message": event["message"],
        }

        # Send the notification message to the WebSocket.
        self.send(text_data=json.dumps(notification))

    def download_message(self, event: dict) -> None:
        """Sends a download update to the client connected through WebSocket.

        Parameters
        ----------
        event : `dict`
            The event dictionary containing the download data.

        """
        # Construct the download message.
        download = {
            "update": "download",
            "unique_id": event["unique_id"],
            "label": event["label"],
            "message": event["message"],
            "status": event["status"],
            "downloaded_bytes": event["downloaded_bytes"],
            "done": event["done"],
            "error": event["error"],
        }

        # Send the download update to the WebSocket.
        self.send(text_data=json.dumps(download))
