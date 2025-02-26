import factory
from django.utils import timezone
from tom_dataproducts.models import ReducedDatum
from tom_targets.tests.factories import SiderealTargetFactory
from .dataproduct import DataProductFactory

class ReducedDatumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReducedDatum
        skip_postgeneration_save = True

    target = factory.SubFactory(SiderealTargetFactory)
    data_product = factory.SubFactory(DataProductFactory)
    data_type = "photometry"
    source_name = "TOM Toolkit"
    source_location = "TOM-TOM Direct Sharing"
    timestamp = factory.LazyFunction(timezone.now)
    value = factory.LazyFunction(
        lambda: {"magnitude": 15.582, "filter": "r", "error": 0.005},
    )

    @factory.post_generation
    def message(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for message in extracted:
                self.message.add(message)