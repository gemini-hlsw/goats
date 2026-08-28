"""Tests the `DRAGONSConsumer.`"""

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from goats_tom.consumers import DRAGONSConsumer


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
async def test_log_message_handling():
    """Tests sending log messages."""
    communicator = _authenticated_communicator(DRAGONSConsumer, "/ws/dragons/")
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
    communicator = _authenticated_communicator(DRAGONSConsumer, "/ws/dragons/")
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
    communicator = _authenticated_communicator(DRAGONSConsumer, "/ws/dragons/")
    await communicator.connect()

    # No messages should be pending
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_anonymous_connection_is_refused():
    """DRAGONS progress names files and runs; not for anonymous connections.

    Same reasoning as `UpdatesConsumer`: WebSockets bypass Django's
    middleware, so the check has to live in the consumer.
    """
    from django.contrib.auth.models import AnonymousUser

    communicator = WebsocketCommunicator(DRAGONSConsumer.as_asgi(), "/ws/dragons/")
    communicator.scope["user"] = AnonymousUser()
    connected, _ = await communicator.connect()
    await communicator.disconnect()
    assert not connected
