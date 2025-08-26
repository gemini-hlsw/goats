from rest_framework.test import APITestCase

from goats_tom.serializers import (
    DRAGONSRecipeFilterSerializer,
)


class TestDRAGONSRecipeFilterSerializer(APITestCase):
    """Test class for `DRAGONSRecipeFilterSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSRecipeFilterSerializer` with valid data."""
        valid_data = {"dragons_run": 1, "observation_type": "BIAS", "include": ["help"]}
        serializer = DRAGONSRecipeFilterSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
