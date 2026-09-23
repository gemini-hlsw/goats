"""Class for DRAGONS updates through a websocket."""

__all__ = ["DRAGONSConsumer"]
import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from goats_tom.realtime.groups import DRAGONS_PREFIX, user_group


class DRAGONSConsumer(WebsocketConsumer):
    """A WebSocket consumer that handles sending update to connected clients on the
    DRAGONS page.

    A reduction's logs and progress go only to the user who started it, so this
    connection joins that user's group alone. An unauthenticated connection
    joins nothing and hears nothing.

    Attributes
    ----------
    group_name : `str | None`
        The group this consumer handles updates for, or `None` when there is no
        signed-in user to listen for.

    """

    def connect(self) -> None:
        """Adds this consumer to the user's DRAGONS group upon WebSocket connection."""
        # `scope["user"]` is populated by Channels' `AuthMiddlewareStack`.
        user = self.scope.get("user")
        self.group_name = user_group(DRAGONS_PREFIX, getattr(user, "pk", None))

        if self.group_name is not None:
            async_to_sync(self.channel_layer.group_add)(
                self.group_name, self.channel_name
            )

        self.accept()

    def disconnect(self, code: int) -> None:
        """Removes this consumer from the DRAGONS group upon WebSocket disconnection.

        Parameters
        ----------
        code : `int`
            Return code to send on disconnect.

        """
        # `getattr`: `disconnect` can run without `connect` having completed.
        if getattr(self, "group_name", None) is not None:
            async_to_sync(self.channel_layer.group_discard)(
                self.group_name,
                self.channel_name,
            )

    def log_message(self, event: dict) -> None:
        """Sends a log message to the client connected through WebSocket.

        Parameters
        ----------
        event : `dict`
            The event dictionary containing the log data.

        """
        # Construct the log message.
        log = {
            "update": "log",
            "message": event["message"],
            "run_id": event["run_id"],
            "recipe_id": event["recipe_id"],
            "reduce_id": event["reduce_id"],
        }

        # Send the log message to the WebSocket.
        self.send(text_data=json.dumps(log))

    def recipe_progress_message(self, event: dict) -> None:
        """Sends a message about recipe progress to the client through a WebSocket.

        Parameters
        ----------
        event : `dict`
            The event dictionary containing the recipe reduce update.

        """
        # Construct the update.
        recipe_progress = {
            "update": "recipe",
            "status": event["status"],
            "recipe_id": event["recipe_id"],
            "reduce_id": event["reduce_id"],
            "run_id": event["run_id"],
        }

        # Send the update to the WebSocket.
        self.send(text_data=json.dumps(recipe_progress))
