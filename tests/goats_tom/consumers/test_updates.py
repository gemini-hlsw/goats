"""Tests for `UpdatesConsumer.`"""

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from goats_tom.consumers import UpdatesConsumer


def _authenticated_communicator(consumer, path, user=None):
    """Build a communicator whose scope carries a signed-in user.

    Both consumers now refuse anonymous connections, so a test that does not
    populate ``scope["user"]`` is correctly rejected. These tests are about
    message handling, not authentication -- the auth behaviour itself is
    covered separately -- so they authenticate and move on.

    A lightweight stand-in rather than a real `User`: the consumers only read
    `is_authenticated` and `pk`, and building a database user would make
    every one of these tests require database access for nothing.
    """

    class _SignedIn:
        is_authenticated = True
        pk = 1

    communicator = WebsocketCommunicator(consumer.as_asgi(), path)
    communicator.scope["user"] = user or _SignedIn()
    return communicator


@pytest.mark.asyncio()
async def test_notification_message_handling():
    """Tests sending and receiving notification messages."""
    communicator = _authenticated_communicator(UpdatesConsumer, "/ws/updates/")
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a notification message to the group which the consumer should receive and
    # handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "updates_group",
        {
            "type": "notification.message",
            "unique_id": "1234",
            "color": "red",
            "label": "Alert",
            "message": "Test notification message",
            "autohide": True
        },
    )

    # Receive and validate the message from the consumer.
    response = await communicator.receive_json_from()
    expected_response = {
        "update": "notification",
        "unique_id": "1234",
        "color": "red",
        "label": "Alert",
        "message": "Test notification message",
        "autohide": True,
        "allowHtml": False,
    }
    assert response == expected_response, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_download_message_handling():
    """Tests sending and receiving download messages."""
    communicator = _authenticated_communicator(UpdatesConsumer, "/ws/updates/")
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a download message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "updates_group",
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
async def test_no_pending_messages():
    """Tests for no pending messages."""
    communicator = _authenticated_communicator(UpdatesConsumer, "/ws/updates/")
    await communicator.connect()

    # No messages should be pending.
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_anonymous_connection_is_refused():
    """An unauthenticated connection must not join the broadcast group.

    Every connection used to be accepted and subscribed to
    `BROADCAST_GROUP` before anyone checked who it was, so a stranger who
    could reach the server received every notification GOATS sent. Harmless
    on a single-user laptop; a leak of one PI's activity on a shared one.

    WebSockets bypass Django's middleware, so `AUTH_STRATEGY = "LOCKED"`
    does **not** close this -- which is the part that makes it easy to miss.
    """
    from django.contrib.auth.models import AnonymousUser

    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
    communicator.scope["user"] = AnonymousUser()
    connected, _ = await communicator.connect()
    await communicator.disconnect()
    assert not connected


@pytest.mark.asyncio()
async def test_missing_user_in_scope_is_refused():
    """Absent auth middleware must fail closed, not open."""
    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
    connected, _ = await communicator.connect()
    await communicator.disconnect()
    assert not connected
