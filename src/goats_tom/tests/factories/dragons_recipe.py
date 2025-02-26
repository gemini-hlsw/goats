import factory
from django.utils import timezone
from goats_tom.models import (
    DRAGONSRecipe,
)
from .dragons_run import DRAGONSRunFactory
from .base_recipe import BaseRecipeFactory


class DRAGONSRecipeFactory(factory.django.DjangoModelFactory):
    """Factory for creating `DRAGONSRecipe` instances for testing."""

    class Meta:
        model = DRAGONSRecipe

    recipe = factory.SubFactory(BaseRecipeFactory)
    dragons_run = factory.SubFactory(DRAGONSRunFactory)
    function_definition = None
    created_at = factory.LazyFunction(timezone.now)
    modified_at = factory.LazyAttribute(lambda o: o.created_at)
    is_default = factory.Faker("boolean")
    observation_type = factory.Iterator(["bias", "flat", "object", "arc"])
    observation_class = factory.Iterator(["partnerCal", "science"])
    object_name = factory.Faker("word")