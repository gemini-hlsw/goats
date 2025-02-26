
import pytest
from django.db.utils import IntegrityError
from goats_tom.tests.factories import (
    BaseRecipeFactory,
    DRAGONSRecipeFactory,
    DRAGONSRunFactory,
)


@pytest.mark.django_db()
class TestDRAGONSRecipe:
    """Test suite for the DRAGONSRecipe model."""

    def test_DRAGONSRecipe_creation(self):
        """Verify that a DRAGONSRecipe instance can be created successfully."""
        dragons_recipe = DRAGONSRecipeFactory()
        assert dragons_recipe.pk is not None, "Should create a DRAGONSRecipe instance."

    def test_base_recipe_link(self):
        """Ensure the DRAGONSRecipe links correctly to a BaseRecipe."""
        base_recipe = BaseRecipeFactory()
        dragons_recipe = DRAGONSRecipeFactory(recipe=base_recipe)
        assert (
            dragons_recipe.recipe == base_recipe
        ), "Should link to the correct BaseRecipe."

    def test_dragons_run_link(self):
        """Ensure the DRAGONSRecipe links correctly to a DRAGONSRun."""
        dragons_run = DRAGONSRunFactory()
        dragons_recipe = DRAGONSRecipeFactory(dragons_run=dragons_run)
        assert (
            dragons_recipe.dragons_run == dragons_run
        ), "Should link to the correct DRAGONSRun."

    def test_function_definition_default(self):
        """Check that the function definition defaults to None."""
        dragons_recipe = DRAGONSRecipeFactory()
        assert (
            dragons_recipe.function_definition is None
        ), "Function definition should default to None."

    def test_active_function_definition(self):
        """Test active function definition retrieval logic."""
        base_recipe = BaseRecipeFactory(function_definition="def base_func(): pass")
        modified_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe, function_definition="def modified_func(): pass",
        )
        assert (
            modified_recipe.active_function_definition == "def modified_func(): pass"
        ), "Should return the modified function definition when set."

        unmodified_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe, function_definition=None,
        )
        assert (
            unmodified_recipe.active_function_definition
            == base_recipe.function_definition
        ), "Should fallback to the base recipe's function definition when none is set."

    def test_unique_together_constraint(self):
        """Test that the unique together constraint on recipe and dragons_run is enforced."""
        first_recipe = DRAGONSRecipeFactory(object_name="test")
        with pytest.raises(IntegrityError):
            DRAGONSRecipeFactory(
                recipe=first_recipe.recipe, dragons_run=first_recipe.dragons_run, observation_type=first_recipe.observation_type, object_name=first_recipe.object_name,
                observation_class=first_recipe.observation_class,
            )

    def test_properties(self):
        """Test that model properties return correct values derived from the base recipe."""
        base_recipe = BaseRecipeFactory(name="ComplexRecipe::Simple",
        )
        dragons_recipe = DRAGONSRecipeFactory(recipe=base_recipe)
        assert (
            dragons_recipe.name == "ComplexRecipe::Simple"
        ), "Name should be retrieved from the base recipe."
        assert (
            dragons_recipe.short_name == "Simple"
        ), "Should correctly extract the short name from the base recipe."
