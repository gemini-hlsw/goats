"""Class that updates and sends a notification."""

__all__ = ["NotificationInstance"]

import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from goats_tom.context.user_context import get_current_user_id

from .groups import BROADCAST_GROUP, UPDATES_PREFIX, user_group

logger = logging.getLogger(__name__)


class NotificationInstance:
    """Class responsible for creating and sending a notification.

    A notification reaches only the user whose work produced it, resolved from
    the request or task context. Use `broadcast` for the rare announcement that
    is addressed to everyone.
    """

    func_type = "notification.message"

    @classmethod
    def create_and_send(
        cls,
        label: str = "",
        message: str = "",
        color: str = "primary",
        autohide: bool = True,
        allow_html: bool = False,
    ) -> None:
        """Creates and sends a notification to the user it belongs to.

        Parameters
        ----------
        message : str, optional
            The body of the notification message to be sent, by default "".
        label : str, optional
            The label of the notification, by default "".
        color : str, optional
            The bootstrap color scheme to apply to the notification, by default
            "primary".
        autohide : bool = True
            Whether the notification should auto-hide after a delay.
        allow_html : bool, optional
            Whether the message should be rendered as HTML instead of plain text.
            Only enable for trusted, static markup, by default ``False``.
        """
        unique_id = f"{uuid.uuid4()}"
        cls._send(unique_id, label, message, color, autohide, allow_html)

    @classmethod
    def broadcast(
        cls,
        label: str = "",
        message: str = "",
        color: str = "primary",
        autohide: bool = True,
        allow_html: bool = False,
    ) -> None:
        """Creates and sends a notification to every connected client.

        Only for announcements about GOATS itself, which belong to nobody in
        particular and have no user context to resolve.

        Parameters
        ----------
        message : str, optional
            The body of the notification message to be sent, by default "".
        label : str, optional
            The label of the notification, by default "".
        color : str, optional
            The bootstrap color scheme to apply to the notification, by default
            "primary".
        autohide : bool = True
            Whether the notification should auto-hide after a delay.
        allow_html : bool, optional
            Whether the message should be rendered as HTML instead of plain text.
            Only enable for trusted, static markup, by default ``False``.
        """
        unique_id = f"{uuid.uuid4()}"
        cls._send(
            unique_id,
            label,
            message,
            color,
            autohide,
            allow_html,
            group=BROADCAST_GROUP,
        )

    @classmethod
    def _send(
        cls,
        unique_id: str,
        label: str,
        message: str,
        color: str,
        autohide: bool,
        allow_html: bool = False,
        *,
        group: str | None = None,
    ) -> None:
        """Sends a notification.

        Parameters
        ----------
        unique_id: str
            The unique ID for the notification.
        message : str
            The body of the notification message to be sent.
        label : str
            The label of the notification.
        color : str
            The bootstrap color scheme to apply to the notification.
        autohide : bool
            Whether the notification should auto-hide after a delay.
        allow_html : bool, optional
            Whether the message should be rendered as HTML instead of plain text.
            Only enable for trusted, static markup, by default ``False``.
        group : str | None, optional
            The group to send to. By default the current user's own group.
        """
        if group is None:
            group = user_group(UPDATES_PREFIX, get_current_user_id())
            if group is None:
                # Dropped rather than broadcast: better lost than shown to all.
                logger.warning(
                    "Dropping notification %r: no user to address it to.", label
                )
                return

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": cls.func_type,
                "unique_id": unique_id,
                "label": label,
                "message": message,
                "color": color,
                "autohide": autohide,
                "allow_html": allow_html,
            },
        )
