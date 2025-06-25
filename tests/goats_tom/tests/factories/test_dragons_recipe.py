import pytest

from goats_tom.tests.factories import (
    BaseRecipeFactory,
    DRAGONSRecipeFactory,
    DRAGONSRunFactory,
)


@pytest.mark.django_db()
class TestDRAGONSRecipeFactory:
    """Class to test the DRAGONSRecipeFactory."""

    def test_factory_with_specific_values(self):
        """Test that the factory correctly applies passed values."""
        base_recipe = BaseRecipeFactory()
        dragons_run = DRAGONSRunFactory()
        custom_function_definition = "def custom_processing(): return 'processed'"

        dragons_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe,
            dragons_run=dragons_run,
            function_definition=custom_function_definition,
        )

        assert (
            dragons_recipe.recipe == base_recipe
        ), "Factory should link to the specified BaseRecipe."
        assert (
            dragons_recipe.dragons_run == dragons_run
        ), "Factory should link to the specified DRAGONSRun."
        assert (
            dragons_recipe.function_definition == custom_function_definition
        ), "Factory should use the specified function definition."
        assert (
            dragons_recipe.function_definition is not None
        ), "Function definition should not be None when explicitly set."

    def test_factory_default_function_definition(self):
        """Test that the factory correctly applies default values."""
        dragons_recipe = DRAGONSRecipeFactory(function_definition=None)
        assert (
            dragons_recipe.function_definition is None
        ), "Function definition should be None by default."

