import factory
from django.utils import timezone

from goats_tom.models import (
    DRAGONSReduce,
)

from .dragons_recipe import DRAGONSRecipeFactory


class DRAGONSReduceFactory(factory.django.DjangoModelFactory):
    """Factory for creating `DRAGONSReduce` instances."""

    class Meta:
        model = DRAGONSReduce

    recipe = factory.SubFactory(DRAGONSRecipeFactory)
    created_at = factory.LazyFunction(timezone.now)
    start_time = None
    end_time = None
    status = "created"
    task_id = None
