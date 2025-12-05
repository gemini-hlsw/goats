import pytest

from goats_tom.serializers import DRAGONSRecipeSerializer
from goats_tom.tests.factories import DRAGONSRecipeFactory


@pytest.mark.django_db
class TestDRAGONSRecipeSerializer:
    def setup_method(self):
        self.recipe = DRAGONSRecipeFactory()

    def test_valid_data(self):
        """Serializer should expose correct read-only data."""
        s = DRAGONSRecipeSerializer(self.recipe)

        assert s.data["observation_type"] == self.recipe.observation_type
        assert s.data["name"] == self.recipe.name
        assert s.data["short_name"] == self.recipe.short_name
        assert (
            s.data["active_function_definition"]
            == self.recipe.active_function_definition
        )

        # write-only field must not appear
        assert "function_definition" not in s.data

    @pytest.mark.parametrize(
        "field,value",
        [
            ("uparms", "['x']"),
            ("function_definition", "def f(): pass"),
            ("reduction_mode", "sq"),
            ("drpkg", "geminidr"),
            ("additional_files", "['M81/file1.fits']"),
            ("ucals", "{'bias':'M81/bias1.fits'}"),
            ("suffix", "_x"),
        ],
    )
    def test_partial_update_individual_fields(self, field, value):
        """Every updatable field should update via partial=True."""
        s = DRAGONSRecipeSerializer(
            self.recipe, data={field: value}, partial=True
        )

        assert s.is_valid(), s.errors
        instance = s.save()

        assert getattr(instance, field) == value

    @pytest.mark.parametrize(
        "field,empty_value,expected",
        [
            ("uparms", "", None),
            ("function_definition", "", None),
            ("additional_files", "", None),
            ("ucals", "", None),
            ("suffix", "", None),
            ("uparms", None, None),
            ("additional_files", None, None),
            ("ucals", None, None),
            ("suffix", None, None),
        ],
    )
    def test_empty_values_become_none(self, field, empty_value, expected):
        """Empty or null-like values should normalize to None in update()."""
        s = DRAGONSRecipeSerializer(
            self.recipe, data={field: empty_value}, partial=True
        )

        assert s.is_valid(), s.errors
        instance = s.save()

        assert getattr(instance, field) is expected

    def test_update_function_definition_and_active_logic(self):
        """active_function_definition should reflect modifications."""
        base_def = self.recipe.recipe.function_definition
        assert self.recipe.active_function_definition == base_def

        s = DRAGONSRecipeSerializer(
            self.recipe, data={"function_definition": "def modified(): pass"}, partial=True
        )
        assert s.is_valid()
        instance = s.save()

        assert instance.function_definition == "def modified(): pass"
        assert instance.active_function_definition == "def modified(): pass"

    def test_reset_function_definition_with_whitespace(self):
        """Whitespace is treated as empty → None."""
        s = DRAGONSRecipeSerializer(
            self.recipe, data={"function_definition": "   "}, partial=True
        )
        assert s.is_valid()
        instance = s.save()

        assert instance.function_definition is None
        assert instance.active_function_definition == self.recipe.recipe.function_definition

    def test_read_only_fields_not_writable(self):
        """Attempting to change read-only fields should have no effect."""
        attempted = {
            "observation_type": "CHANGED",
            "name": "CHANGED",
            "short_name": "CHANGED",
            "version": "CHANGED",
            "recipes_module_name": "CHANGED",
        }

        s = DRAGONSRecipeSerializer(self.recipe, data=attempted, partial=True)
        # These should simply be ignored, not errors
        assert s.is_valid(), s.errors
        instance = s.save()

        assert instance.observation_type == self.recipe.observation_type
        assert instance.name == self.recipe.name
        assert instance.short_name == self.recipe.short_name
        assert instance.version == self.recipe.version
