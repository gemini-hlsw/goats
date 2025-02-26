import factory
from goats_tom.models import (
    RecipesModule
)


class RecipesModuleFactory(factory.django.DjangoModelFactory):
    """Factory for creating `RecipesModule` instances for testing."""

    class Meta:
        model = RecipesModule

    name = factory.Faker("word")
    version = factory.Faker("numerify", text='#.#.#')
    instrument = factory.Faker("word")