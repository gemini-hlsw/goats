"""Tests the `DRAGONSConsumer.`"""

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from goats_tom.consumers import DRAGONSConsumer


@pytest.mark.asyncio()
async def test_log_message_handling():
    """Tests sending log messages."""
    communicator = WebsocketCommunicator(DRAGONSConsumer.as_asgi(), "/ws/dragons/")
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "dragons_group",
        {
            "type": "log.message",
            "message": "Test log message",
            "run_id": 1,
            "recipe_id": 2,
            "reduce_id": 3,
        },
    )

    # Receive and validate the message from the consumer.
    response = await communicator.receive_json_from()
    expected_response = {
        "update": "log",
        "message": "Test log message",
        "run_id": 1,
        "recipe_id": 2,
        "reduce_id": 3,
    }
    assert response == expected_response, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_recipe_progress_handling():
    """Tests sending recipe progress."""
    communicator = WebsocketCommunicator(DRAGONSConsumer.as_asgi(), "/ws/dragons/")
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "dragons_group",
        {
            "type": "recipe.progress.message",
            "status": "done",
            "run_id": 1,
            "recipe_id": 2,
            "reduce_id": 3,
        },
    )

    # Receive and validate the message from the consumer.
    response = await communicator.receive_json_from()
    expected_response = {
        "update": "recipe",
        "status": "done",
        "run_id": 1,
        "recipe_id": 2,
        "reduce_id": 3,
    }
    assert response == expected_response, "Incorrect response received"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_no_pending_messages():
    """Tests for pending messages."""
    communicator = WebsocketCommunicator(DRAGONSConsumer.as_asgi(), "/ws/dragons/")
    await communicator.connect()

    # No messages should be pending
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()
