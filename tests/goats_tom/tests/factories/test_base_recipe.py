import pytest

from goats_tom.tests.factories import (
    BaseRecipeFactory,
    RecipesModuleFactory,
)


@pytest.mark.django_db()
class TestBaseRecipeFactory:
    """Class to test the BaseRecipeFactory."""

    def test_factory_with_specific_values(self):
        """Test that the factory correctly applies passed values."""
        recipes_module = RecipesModuleFactory(version="32.2.0")
        recipe = BaseRecipeFactory(name="Test Recipe", recipes_module=recipes_module,
        )
        assert recipe.name == "Test Recipe", "Factory should use the specified name."
        assert recipe.version == "32.2.0", "Factory should use the specified version."
