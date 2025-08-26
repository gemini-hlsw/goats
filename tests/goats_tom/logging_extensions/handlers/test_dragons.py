"""Module for testing DRAGONS logging handler."""

import logging
from unittest import TestCase, mock

from goats_tom.logging_extensions.handlers import DRAGONSHandler


class TestDRAGONSHandler(TestCase):
    """Test DRAGONS logging handler."""

    def setUp(self):
        # Patch the get_channel_layer to return a mock.
        self.patcher = mock.patch(
            "goats_tom.logging_extensions.handlers.dragons.get_channel_layer",
        )
        self.mock_get_channel_layer = self.patcher.start()
        self.mock_channel_layer = mock.Mock()
        self.mock_get_channel_layer.return_value = self.mock_channel_layer
        self.mock_channel_layer.group_send = mock.AsyncMock()

        # Create an instance of the handler.
        self.handler = DRAGONSHandler(recipe_id=123, reduce_id=456, run_id=789)

    def tearDown(self):
        self.patcher.stop()

    def test_initialization(self):
        """Test that the handler initializes with correct recipe and reduce IDs and a
        channel layer.
        """
        self.assertEqual(self.handler.recipe_id, 123)
        self.assertEqual(self.handler.reduce_id, 456)
        self.assertIsNotNone(self.handler.channel_layer)

    def test_emit(self):
        """Test that the emit method sends the correct message format and data."""
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Test log message",
            args=None,
            exc_info=None,
        )
        formatter = logging.Formatter("%(message)s")
        self.handler.setFormatter(formatter)
        self.handler.emit(log_record)

        expected_message = {
            "type": "log.message",
            "message": "Test log message",
            "recipe_id": 123,
            "reduce_id": 456,
            "run_id": 789,
        }
        self.mock_channel_layer.group_send.assert_called_once_with(
            "dragons_group", expected_message,
        )

    def test_emit_with_failure(self):
        """Test behavior when channel layer fails to send a message."""
        self.mock_channel_layer.group_send.side_effect = Exception(
            "Channel layer error",
        )
        log_record = logging.LogRecord(
            name="test_failure",
            level=logging.ERROR,
            pathname=__file__,
            lineno=11,
            msg="Error log message",
            args=None,
            exc_info=None,
        )
        # No need to assert here, just ensuring no unhandled exceptions
        try:
            self.handler.emit(log_record)
        except Exception as e:
            self.fail(f"emit raised an exception: {e}")
