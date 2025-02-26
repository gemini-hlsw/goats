from goats_tom.serializers import (
    DRAGONSFileFilterSerializer,
)
from rest_framework.test import APITestCase


class TestDRAGONSFileFilterSerializer(APITestCase):
    """Test class for `DRAGONSFileFilterSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSFileFilterSerializer` with valid data."""
        valid_data = {
            "dragons_run": 1,
            "include": ["astrodata_descriptors"],
        }
        serializer = DRAGONSFileFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())

    def test_invalid_data(self):
        """Test `DRAGONSFileFilterSerializer` with invalid data."""
        invalid_data = {"include": ["invalid_option"]}
        serializer = DRAGONSFileFilterSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())