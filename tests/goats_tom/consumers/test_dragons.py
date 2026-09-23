"""Tests the `DRAGONSConsumer.`"""

from types import SimpleNamespace

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from goats_tom.consumers import DRAGONSConsumer
from goats_tom.realtime.groups import DRAGONS_PREFIX, user_group

USER_ID = 7


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
    communicator = WebsocketCommunicator(DRAGONSConsumer.as_asgi(), "/ws/dragons/")
    communicator.scope["user"] = SimpleNamespace(pk=user_id, is_authenticated=True)
    return communicator


@pytest.mark.asyncio()
async def test_log_message_handling():
    """Tests sending log messages."""
    communicator = connect_as(USER_ID)
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        user_group(DRAGONS_PREFIX, USER_ID),
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
    communicator = connect_as(USER_ID)
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    # Send a message to the group which the consumer should receive and handle.
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        user_group(DRAGONS_PREFIX, USER_ID),
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
async def test_another_users_reduction_is_not_delivered():
    """A reduction started by someone else never reaches this connection."""
    communicator = connect_as(USER_ID)
    await communicator.connect()

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        user_group(DRAGONS_PREFIX, USER_ID + 1),
        {
            "type": "log.message",
            "message": "Someone else's files",
            "run_id": 1,
            "recipe_id": 2,
            "reduce_id": 3,
        },
    )

    assert await communicator.receive_nothing() is True, "Another user's log leaked"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_an_anonymous_connection_joins_nothing():
    """With no signed-in user there is no group to listen on."""
    communicator = connect_as(None)
    connected, _ = await communicator.connect()
    assert connected, "Connection to WebSocket failed"

    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()


@pytest.mark.asyncio()
async def test_no_pending_messages():
    """Tests for pending messages."""
    communicator = connect_as(USER_ID)
    await communicator.connect()

    # No messages should be pending
    assert await communicator.receive_nothing() is True, "Unexpected message pending"

    await communicator.disconnect()
