"""Tests for `NotificationInstance`."""

from unittest.mock import patch

from goats_tom.realtime import NotificationInstance


def test_notification_instance():
    """Tests creating and sending a notification."""
    with patch.object(NotificationInstance, "_send") as mock_send:
        # Create and send a notification
        NotificationInstance.create_and_send(
            label="Alert", message="Test notification", color="warning",
        )

        # Verify that _send was called with the correct parameters.
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        unique_id, label, message, color = args

        assert label == "Alert", "Label not set correctly"
        assert message == "Test notification", "Message not set correctly"
        assert color == "warning", "Color not set correctly"
        assert isinstance(unique_id, str), "Unique ID not set correctly"
