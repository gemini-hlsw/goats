"""Class for updates through a websocket for all webpages."""

__all__ = ["UpdatesConsumer"]

import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from goats_tom.realtime.groups import BROADCAST_GROUP, UPDATES_PREFIX, user_group


class UpdatesConsumer(WebsocketConsumer):
    """A WebSocket consumer that handles sending updates to
    connected clients on all pages.

    Each connection joins two groups: the broadcast one, which carries
    announcements about GOATS itself, and the signed-in user's own, which
    carries everything their work produces.

    Attributes
    ----------
    groups_joined : `list[str]`
        The groups this connection was added to.

    """

    def connect(self) -> None:
        """Adds this consumer to the updates groups upon WebSocket connection."""
        # `scope["user"]` is populated by Channels' `AuthMiddlewareStack`.
        user = self.scope.get("user")
        own_group = user_group(UPDATES_PREFIX, getattr(user, "pk", None))

        self.groups_joined = [BROADCAST_GROUP]
        if own_group is not None:
            self.groups_joined.append(own_group)

        for group in self.groups_joined:
            async_to_sync(self.channel_layer.group_add)(group, self.channel_name)

        self.accept()

    def disconnect(self, code: int) -> None:
        """Removes this consumer from the updates groups upon WebSocket disconnection.

        Parameters
        ----------
        code : `int`
            Return code to send on disconnect.

        """
        # `getattr`: `disconnect` can run without `connect` having completed.
        for group in getattr(self, "groups_joined", []):
            async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)

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
            "autohide": event["autohide"],
            "allowHtml": event.get("allow_html", False),
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
