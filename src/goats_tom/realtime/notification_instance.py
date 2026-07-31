"""Class that updates and sends a notification."""

__all__ = ["NotificationInstance"]

import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import BROADCAST_GROUP, user_group_name

logger = logging.getLogger(__name__)


class NotificationInstance:
    """Class responsible for creating and sending a notification.

    By default a notification goes to every connected client (see
    `group_name`), which is how all of GOATS' existing notifications behave.
    Pass `user` to `create_and_send` to deliver it to one person instead --
    used where a notification names another user or reveals group activity,
    which should not be broadcast to everyone signed in.
    """

    group_name = BROADCAST_GROUP
    func_type = "notification.message"

    @classmethod
    def create_and_send(
        cls,
        label: str = "",
        message: str = "",
        color: str = "primary",
        autohide: bool = True,
        allow_html: bool = False,
        user=None,
    ) -> None:
        """Creates and sends a notification.

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
        user : `django.contrib.auth.models.User`, optional
            Deliver only to this user's own connections instead of to every
            connected client. `None` (the default) preserves the original
            broadcast behavior, so existing callers are unaffected.

            If a `user` is given but cannot be addressed (anonymous, or
            unsaved), the notification is dropped rather than broadcast --
            see `goats_tom.realtime.groups.user_group_name`. Falling back to
            a broadcast would show a message intended for one person to
            everybody, which is the exact failure this parameter exists to
            avoid.
        """
        unique_id = f"{uuid.uuid4()}"
        cls._send(
            unique_id, label, message, color, autohide, allow_html, user=user
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
        user=None,
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
        user : `django.contrib.auth.models.User`, optional
            Target a single user rather than broadcasting. Keyword-only in
            practice: the six positional parameters above are left in their
            original order so existing callers and tests are unaffected.
        """
        if user is None:
            target_group = cls.group_name
        else:
            target_group = user_group_name(user)
            if target_group is None:
                logger.warning(
                    "Dropping notification %r: a specific user was given but "
                    "could not be addressed.",
                    label,
                )
                return

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            target_group,
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
