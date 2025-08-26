from rest_framework.test import APITestCase

from goats_tom.serializers import (
    DRAGONSRecipeSerializer,
)
from goats_tom.tests.factories import (
    DRAGONSRecipeFactory,
)


class TestDRAGONSRecipeSerializer(APITestCase):
    """Test class for `DRAGONSRecipeSerializer`."""

    def setUp(self):
        self.recipe = DRAGONSRecipeFactory()

    def test_valid_data(self):
        """Test `DRAGONSRecipeSerializer` with valid data."""
        serializer = DRAGONSRecipeSerializer(self.recipe)

        self.assertEqual(serializer.data["observation_type"], self.recipe.observation_type)
        self.assertEqual(serializer.data["name"], self.recipe.name)
        self.assertEqual(
            serializer.data["active_function_definition"], self.recipe.active_function_definition,
        )
        self.assertEqual(serializer.data["short_name"], self.recipe.short_name)

    def test_partial_update(self):
        """Test partial update of `DRAGONSRecipe`."""
        partial_data = {"function_definition": "Updated function definition", "uparms": "test"}
        serializer = DRAGONSRecipeSerializer(self.recipe, data=partial_data, partial=True)

        self.assertTrue(serializer.is_valid())
        updated_instance = serializer.save()
        self.assertEqual(
            updated_instance.active_function_definition, "Updated function definition",
        )
        self.assertEqual(
            updated_instance.function_definition, "Updated function definition",
        )
        self.assertEqual(
            updated_instance.uparms, "test",
        )

    def test_update_with_whitespace_only(self):
        """Test updating function definition with whitespace only to trigger reset."""
        data = {"function_definition": "   "}
        serializer = DRAGONSRecipeSerializer(self.recipe, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated_instance = serializer.save()
        self.assertIsNone(updated_instance.function_definition)

    def test_function_definition_write_only(self):
        """Test that 'function_definition' is write-only and not included in the output.
        """
        serializer = DRAGONSRecipeSerializer(self.recipe)
        self.assertNotIn("function_definition", serializer.data)
