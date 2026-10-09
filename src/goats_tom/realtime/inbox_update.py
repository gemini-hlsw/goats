"""Class that pushes inbox changes to a user's open pages."""

__all__ = ["InboxUpdate"]

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import UPDATES_PREFIX, user_group


class InboxUpdate:
    """Sends the unread count, and optionally a new notification, to one user."""

    func_type = "inbox.message"

    @classmethod
    def send(
        cls,
        user_id: int,
        unread: int,
        notification: dict | None = None,
        read_ids: list[int] | None = None,
    ) -> None:
        """Push an inbox update.

        Parameters
        ----------
        user_id : int
            The recipient.
        unread : int
            Their unread count after the change.
        notification : dict | None, optional
            The new notification to show, if one was just created.
        read_ids : list[int] | None, optional
            Notifications that were just read or resolved.
        """
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            user_group(UPDATES_PREFIX, user_id),
            {
                "type": cls.func_type,
                "unread": unread,
                "notification": notification,
                "read_ids": read_ids or [],
            },
        )
