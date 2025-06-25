from rest_framework.test import APITestCase

from goats_tom.serializers import (
    DRAGONSRunFilterSerializer,
    DRAGONSRunSerializer,
)


class TestDRAGONSRunFilterSerializer(APITestCase):
    """Test class for `DRAGONSRunFilterSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSRunFilterSerializer` with valid data."""
        valid_data = {"observation_record": 1}
        serializer = DRAGONSRunFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_data(self):
        """Test `DRAGONSRunSerializer` with invalid data."""
        invalid_data = {
            "config_filename": "",
            "output_directory": "",
            "cal_manager_filename": "",
            "log_filename": "",
        }
        serializer = DRAGONSRunSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config_filename", serializer.errors)
        self.assertIn("cal_manager_filename", serializer.errors)
