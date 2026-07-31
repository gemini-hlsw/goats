"""Class for updates through a websocket for all webpages."""

__all__ = ["UpdatesConsumer"]

import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from goats_tom.realtime.groups import BROADCAST_GROUP, user_group_name


class UpdatesConsumer(WebsocketConsumer):
    """A WebSocket consumer that handles sending updates to
    connected clients on all pages.

    Each connection joins two channel groups:

    - `group_name`, shared by every connected client, which is where all of
      GOATS' broadcast notifications go.
    - a private group named for the signed-in user, so a notification can be
      addressed to one person (see
      `goats_tom.realtime.NotificationInstance`'s `user` argument). Needed
      because some notifications name another user or reveal group activity,
      which shouldn't reach everybody signed in.

    Both are joined, rather than the private one replacing the broadcast
    group, so existing notifications keep working unchanged.

    Attributes
    ----------
    group_name : `str`
        The name of the broadcast group that this consumer handles updates
        for.

    """

    group_name = BROADCAST_GROUP

    def connect(self) -> None:
        """Adds this consumer to the updates groups upon WebSocket connection."""
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)

        # `scope["user"]` is populated by Channels' `AuthMiddlewareStack`
        # (see the project's `asgi.py`). Read with `.get` and checked for
        # `None`, since it is absent entirely for an unauthenticated
        # connection -- and in tests that drive the consumer directly without
        # the auth middleware -- in which case there is simply no private
        # group to join.
        self.user_group_name = user_group_name(self.scope.get("user"))
        if self.user_group_name is not None:
            async_to_sync(self.channel_layer.group_add)(
                self.user_group_name, self.channel_name
            )

        self.accept()

    def disconnect(self, code: int) -> None:
        """Removes this consumer from the updates groups upon WebSocket disconnection.

        Parameters
        ----------
        code : `int`
            Return code to send on disconnect.

        """
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name,
            self.channel_name,
        )

        # `getattr` rather than a plain attribute access: `disconnect` can be
        # called without `connect` having completed, in which case the
        # attribute was never set.
        user_group = getattr(self, "user_group_name", None)
        if user_group is not None:
            async_to_sync(self.channel_layer.group_discard)(
                user_group,
                self.channel_name,
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
