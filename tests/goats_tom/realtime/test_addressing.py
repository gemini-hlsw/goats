"""Tests that every real-time sender addresses the user it belongs to."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from goats_tom.context.user_context import user_id_context
from goats_tom.logging_extensions.handlers import DRAGONSHandler
from goats_tom.logging_extensions.handlers import dragons as dragons_handler_module
from goats_tom.realtime import DownloadState, DRAGONSProgress, NotificationInstance
from goats_tom.realtime import download_state as download_state_module
from goats_tom.realtime import dragons_progress as dragons_progress_module
from goats_tom.realtime import notification_instance as notification_module
from goats_tom.realtime.groups import BROADCAST_GROUP

USER_ID = 42

SENDER_MODULES = (
    notification_module,
    download_state_module,
    dragons_progress_module,
    dragons_handler_module,
)


@pytest.fixture
def channel_layer(monkeypatch):
    """A channel layer that records what group each message was sent to."""
    layer = SimpleNamespace(group_send=AsyncMock())
    for module in SENDER_MODULES:
        monkeypatch.setattr(module, "get_channel_layer", lambda: layer)
    return layer


def groups_sent_to(channel_layer) -> list[str]:
    """The groups the layer was asked to send to, in order."""
    return [call.args[0] for call in channel_layer.group_send.await_args_list]


def log_record() -> logging.LogRecord:
    """A record for the DRAGONS handler to format and send."""
    return logging.LogRecord(
        name="dragons",
        level=21,
        pathname=__file__,
        lineno=1,
        msg="reducing",
        args=(),
        exc_info=None,
    )


def test_a_notification_goes_to_its_own_user(channel_layer) -> None:
    """A notification reaches the user whose work produced it."""
    with user_id_context(USER_ID):
        NotificationInstance.create_and_send(label="Done", message="Reduced.")

    assert groups_sent_to(channel_layer) == [f"updates_user_{USER_ID}"]


def test_a_notification_without_a_user_is_dropped(channel_layer) -> None:
    """With no user to address, the notification is lost rather than broadcast."""
    NotificationInstance.create_and_send(label="Done", message="Reduced.")

    assert groups_sent_to(channel_layer) == []


def test_a_broadcast_reaches_everyone(channel_layer) -> None:
    """An announcement about GOATS itself still goes to the broadcast group."""
    NotificationInstance.broadcast(label="Update available", message="3.0.1")

    assert groups_sent_to(channel_layer) == [BROADCAST_GROUP]


def test_a_download_update_goes_to_its_own_user(channel_layer) -> None:
    """Download progress reaches the user who started the download."""
    with user_id_context(USER_ID):
        DownloadState().update_and_send(label="Files", status="Started")

    assert groups_sent_to(channel_layer) == [f"updates_user_{USER_ID}"]


def test_a_download_update_without_a_user_is_dropped(channel_layer) -> None:
    """With no user to address, the download update is lost."""
    DownloadState().update_and_send(label="Files", status="Started")

    assert groups_sent_to(channel_layer) == []


def test_reduction_progress_goes_to_its_own_user(channel_layer) -> None:
    """Recipe progress reaches the user who started the reduction."""
    with user_id_context(USER_ID):
        DRAGONSProgress._send("running", run_id=1, recipe_id=2, reduce_id=3)

    assert groups_sent_to(channel_layer) == [f"dragons_user_{USER_ID}"]


def test_reduction_progress_without_a_user_is_dropped(channel_layer) -> None:
    """With no user to address, the progress update is lost."""
    DRAGONSProgress._send("running", run_id=1, recipe_id=2, reduce_id=3)

    assert groups_sent_to(channel_layer) == []


def test_reduction_logs_go_to_their_own_user(channel_layer) -> None:
    """A reduction's logs reach the user who started it."""
    with user_id_context(USER_ID):
        handler = DRAGONSHandler(recipe_id=2, reduce_id=3, run_id=1)
    handler.emit(log_record())

    assert groups_sent_to(channel_layer) == [f"dragons_user_{USER_ID}"]


def test_reduction_logs_without_a_user_are_dropped(channel_layer) -> None:
    """A reduction with no user behind it sends its logs nowhere."""
    handler = DRAGONSHandler(recipe_id=2, reduce_id=3, run_id=1)
    handler.emit(log_record())

    assert groups_sent_to(channel_layer) == []


def test_a_handler_keeps_its_own_user(channel_layer) -> None:
    """Records handed over by another reduction's thread go to this user.

    The handler is attached to a logger DRAGONS shares, so it is handed records
    emitted elsewhere; its user is fixed when it is built, like its run.
    """
    with user_id_context(USER_ID):
        handler = DRAGONSHandler(recipe_id=2, reduce_id=3, run_id=1)

    with user_id_context(USER_ID + 1):
        handler.emit(log_record())

    assert groups_sent_to(channel_layer) == [f"dragons_user_{USER_ID}"]
