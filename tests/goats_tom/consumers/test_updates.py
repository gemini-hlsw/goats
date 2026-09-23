"""Tests for `UpdatesConsumer.`"""

from types import SimpleNamespace

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from goats_tom.consumers import UpdatesConsumer
from goats_tom.realtime.groups import BROADCAST_GROUP, UPDATES_PREFIX, user_group

USER_ID = 7

NOTIFICATION = {
    "type": "notification.message",
    "unique_id": "1234",
    "color": "red",
    "label": "Alert",
    "message": "Test notification message",
    "autohide": True,
}
EXPECTED_NOTIFICATION = {
    "update": "notification",
    "unique_id": "1234",
    "color": "red",
    "label": "Alert",
    "message": "Test notification message",
    "autohide": True,
    "allowHtml": False,
}


def connect_as(user_id: int | None) -> WebsocketCommunicator:
    """A communicator carrying the user `AuthMiddlewareStack` would have set.

    Parameters
    ----------
    user_id : `int | None`
        The signed-in user, or `None` for an anonymous connection.

    Returns
    -------
    `WebsocketCommunicator`
        The communicator, not yet connected.
    """
    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
    communicator.scope["user"] = SimpleNamespace(pk=user_id, is_authenticated=True)
    return communicator


@pytest.mark.asyncio()
async def test_notification_message_handling():
    """Tests sending and receiving notification messages."""
    communicator = connect_as(USER_ID)
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a notification message to the group which the consumer should receive and
    # handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(user_group(UPDATES_PREFIX, USER_ID), NOTIFICATION)

    # Receive and validate the message from the consumer.
    response = await communicator.receive_json_from()
    assert response == EXPECTED_NOTIFICATION, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_download_message_handling():
    """Tests sending and receiving download messages."""
    communicator = connect_as(USER_ID)
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a download message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        user_group(UPDATES_PREFIX, USER_ID),
        {
            "type": "download.message",
            "unique_id": "5678",
            "label": "Download Task",
            "message": "Download in progress",
            "status": "In Progress",
            "downloaded_bytes": "2 KB",
            "done": False,
            "error": False,
        },
    )

    # Receive and validate the message from the consumer.
    response = await communicator.receive_json_from()
    expected_response = {
        "update": "download",
        "unique_id": "5678",
        "label": "Download Task",
        "message": "Download in progress",
        "status": "In Progress",
        "downloaded_bytes": "2 KB",
        "done": False,
        "error": False,
    }
    assert response == expected_response, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_another_users_notification_is_not_delivered():
    """A notification addressed to someone else never reaches this connection."""
    communicator = connect_as(USER_ID)
    await communicator.connect()

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        user_group(UPDATES_PREFIX, USER_ID + 1), NOTIFICATION
    )

    assert await communicator.receive_nothing() is True, "Another user's message leaked"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_a_broadcast_reaches_everyone():
    """Announcements about GOATS itself still go to every connection."""
    communicator = connect_as(USER_ID)
    await communicator.connect()

    channel_layer = get_channel_layer()
    await channel_layer.group_send(BROADCAST_GROUP, NOTIFICATION)

    response = await communicator.receive_json_from()
    assert response == EXPECTED_NOTIFICATION, "Broadcast not received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_an_anonymous_connection_hears_only_broadcasts():
    """With no signed-in user there is no private group to join."""
    communicator = connect_as(None)
    await communicator.connect()

    channel_layer = get_channel_layer()
    await channel_layer.group_send(user_group(UPDATES_PREFIX, USER_ID), NOTIFICATION)
    assert await communicator.receive_nothing() is True, "A user's message leaked"

    await channel_layer.group_send(BROADCAST_GROUP, NOTIFICATION)
    assert await communicator.receive_json_from() == EXPECTED_NOTIFICATION

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_no_pending_messages():
    """Tests for no pending messages."""
    communicator = connect_as(USER_ID)
    await communicator.connect()

    # No messages should be pending.
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()
