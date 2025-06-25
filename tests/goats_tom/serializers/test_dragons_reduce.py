from rest_framework.test import APITestCase

from goats_tom.serializers import (
    DRAGONSReduceSerializer,
)
from goats_tom.tests.factories import (
    DRAGONSRecipeFactory,
)


class TestDRAGONSReduceSerializer(APITestCase):
    """Test class for `DRAGONSReduceSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSReduceSerializer` with valid data."""
        recipe = DRAGONSRecipeFactory()
        valid_data = {"recipe_id": recipe.id}

        serializer = DRAGONSReduceSerializer(data=valid_data)
        self.assertTrue(
            serializer.is_valid(),
            msg=f"Serializer should be valid. Errors: {serializer.errors}",
        )

        reduction = serializer.save()
        self.assertIsNotNone(reduction.id, "Reduction should have an ID after saving.")
        self.assertEqual(
            reduction.recipe_id,
            recipe.id,
            "Reduction recipe ID should match the input.",
        )

    def test_invalid_data(self):
        """Test `DRAGONSReduceSerializer` with invalid data."""
        invalid_data = {"recipe_id": 999999}  # Assuming this ID does not exist

        serializer = DRAGONSReduceSerializer(data=invalid_data)
        self.assertFalse(
            serializer.is_valid(),
            "Serializer should not be valid with a non-existent recipe ID.",
        )
        self.assertIn(
            "recipe_id", serializer.errors, "Error key should be 'recipe_id'.",
        )
