"""Tests for `InboxUpdate`."""

from unittest.mock import AsyncMock, patch

from goats_tom.realtime import InboxUpdate


def test_inbox_update_goes_to_the_users_group():
    layer = AsyncMock()
    with patch("goats_tom.realtime.inbox_update.get_channel_layer", return_value=layer):
        InboxUpdate.send(7, 3, {"id": 1})

    layer.group_send.assert_awaited_once_with(
        "updates_user_7",
        {"type": "inbox.message", "unread": 3, "notification": {"id": 1}, "read_ids": []},
    )
