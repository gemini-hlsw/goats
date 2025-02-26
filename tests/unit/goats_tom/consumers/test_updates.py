"""Tests for `UpdatesConsumer.`"""

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from goats_tom.consumers import UpdatesConsumer


@pytest.mark.asyncio()
async def test_notification_message_handling():
    """Tests sending and receiving notification messages."""
    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
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
    }
    assert response == expected_response, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_download_message_handling():
    """Tests sending and receiving download messages."""
    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
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
    communicator = WebsocketCommunicator(UpdatesConsumer.as_asgi(), "/ws/updates/")
    await communicator.connect()

    # No messages should be pending.
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()
