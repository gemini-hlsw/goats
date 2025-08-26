from django.test import TestCase

from goats_tom.serializers import AstroDatalabSerializer
from goats_tom.tests.factories import DataProductFactory


class AstroDatalabSerializerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.data_product = DataProductFactory()

    def test_valid_data(self):
        """Test serializer with valid data_product ID."""
        valid_data = {"data_product": self.data_product.id}
        serializer = AstroDatalabSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid(), msg=serializer.errors)

    def test_invalid_data_product(self):
        """Test serializer with invalid (nonexistent) data_product ID."""
        invalid_data = {"data_product": 2}
        serializer = AstroDatalabSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("data_product", serializer.errors)
