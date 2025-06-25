from rest_framework.test import APITestCase

from goats_tom.serializers import (
    DRAGONSFileSerializer,
)
from goats_tom.tests.factories import (
    DRAGONSFileFactory,
)


class TestDRAGONSFileSerializer(APITestCase):
    """Test class for `DRAGONSFileSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSFileSerializer` with valid data."""
        dragons_file = DRAGONSFileFactory()
        serializer = DRAGONSFileSerializer(dragons_file)

        self.assertEqual(
            serializer.data["product_id"], dragons_file.product_id,
        )
