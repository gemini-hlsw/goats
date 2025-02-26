from goats_tom.serializers import (
    DRAGONSReduceFilterSerializer,
)
from rest_framework.test import APITestCase


class TestDRAGONSReduceFilterSerializer(APITestCase):
    """Test class for `DRAGONSReduceFilterSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSReduceFilterSerializer` with valid data."""
        valid_data = {"status": ["running", "queued"], "not_finished": True, "run": 1}
        serializer = DRAGONSReduceFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_status(self):
        """Test `DRAGONSReduceFilterSerializer` with invalid status."""
        invalid_data = {"status": ["invalid_status"], "not_finished": True, "run": 1}
        serializer = DRAGONSReduceFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_invalid_not_finished(self):
        """Test `DRAGONSReduceFilterSerializer` with invalid not_finished."""
        invalid_data = {
            "status": ["running"],
            "not_finished": "invalid_boolean",
            "run": 1,
        }
        serializer = DRAGONSReduceFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("not_finished", serializer.errors)

    def test_invalid_run(self):
        """Test `DRAGONSReduceFilterSerializer` with invalid run."""
        invalid_data = {
            "status": ["running"],
            "not_finished": True,
            "run": "invalid_integer",
        }
        serializer = DRAGONSReduceFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("run", serializer.errors)

    def test_partial_valid_data(self):
        """Test `DRAGONSReduceFilterSerializer` with partial valid data."""
        valid_data = {"status": ["done"]}
        serializer = DRAGONSReduceFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

    def test_empty_data(self):
        """Test `DRAGONSReduceFilterSerializer` with empty data."""
        valid_data = {}
        serializer = DRAGONSReduceFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
