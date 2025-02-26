import factory
from goats_tom.models import (
    BaseRecipe,
)
from .recipes_module import RecipesModuleFactory


class BaseRecipeFactory(factory.django.DjangoModelFactory):
    """Factory for creating `BaseRecipe` instances for testing."""

    class Meta:
        model = BaseRecipe

    name = factory.Sequence(lambda n: f"Recipe{n}")
    function_definition = factory.Faker("paragraph")
    recipes_module = factory.SubFactory(RecipesModuleFactory)
