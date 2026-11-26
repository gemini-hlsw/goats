"""Tests for the progress of a request to GPP."""

from unittest.mock import AsyncMock, patch

from goats_tom.realtime import GPPProgress


def _sent(user_id, progress_id):
    layer = AsyncMock()
    with patch("goats_tom.realtime.gpp_progress.get_channel_layer", return_value=layer):
        GPPProgress(user_id, progress_id).send(
            "Update Observation", "Success", "o-1 updated"
        )
    return layer.group_send


def test_sends_the_step_to_the_user_who_made_the_request():
    group_send = _sent(7, "p-1")

    group_send.assert_awaited_once_with(
        "updates_user_7",
        {
            "type": "gpp.progress",
            "progress_id": "p-1",
            "stage": "Update Observation",
            "status": "Success",
            "message": "o-1 updated",
        },
    )


def test_sends_nothing_without_a_request_id():
    """A request that did not ask for progress, such as one from a test, gets none."""
    _sent(7, None).assert_not_awaited()
    _sent(7, "").assert_not_awaited()


def test_sends_nothing_without_a_user():
    """Progress meant for one user is dropped rather than broadcast."""
    _sent(None, "p-1").assert_not_awaited()


def test_a_failed_send_does_not_fail_the_request():
    layer = AsyncMock()
    layer.group_send.side_effect = RuntimeError("redis down")
    with patch("goats_tom.realtime.gpp_progress.get_channel_layer", return_value=layer):
        GPPProgress(7, "p-1").send("Update Observation", "Success", "o-1 updated")
