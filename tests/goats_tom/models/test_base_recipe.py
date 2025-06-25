
import pytest
from django.core.exceptions import ValidationError

from goats_tom.models import BaseRecipe
from goats_tom.tests.factories import (
    BaseRecipeFactory,
)


@pytest.mark.django_db()
class TestBaseRecipe:
    """Tests for the BaseRecipe model."""

    def test_factory_creation(self):
        """Ensure the BaseRecipe factory correctly creates a new instance."""
        base_recipe = BaseRecipeFactory()
        assert (
            base_recipe.pk is not None
        ), "BaseRecipe should be created with a primary key."
        assert isinstance(
            base_recipe, BaseRecipe,
        ), "Factory should create a BaseRecipe instance."

    def test_short_name_extraction(self):
        """Test the extraction of short_name from the name attribute."""
        base_recipe_with_short = BaseRecipeFactory(name="Recipe::ShortName")
        assert (
            base_recipe_with_short.short_name == "ShortName"
        ), "Should correctly extract 'ShortName'."

        base_recipe_without_short = BaseRecipeFactory(name="RecipeWithoutDelimiter")
        assert (
            base_recipe_without_short.short_name == "Unknown"
        ), "Should return 'Unknown' if delimiter '::' is absent."

    def test_unique_constraints(self):
        """Ensure that BaseRecipe respects its unique-together constraint."""
        base_recipe = BaseRecipeFactory()
        with pytest.raises(ValidationError):
            duplicate_recipe = BaseRecipeFactory.build(
                name=base_recipe.name,
            )
            duplicate_recipe.full_clean()
