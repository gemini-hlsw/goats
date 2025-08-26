import uuid

import factory
from tom_dataproducts.models import DataProduct
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


class DataProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataProduct

    product_id = factory.LazyAttribute(
        lambda o: (
            f"{o.target.name}__{o.observation_record.observation_id}__{uuid.uuid4()}"
        )
    )
    target = factory.SubFactory(SiderealTargetFactory)
    # Ensure observation_record is associated with the same target as
    # DataProduct
    observation_record = factory.SubFactory(
        ObservingRecordFactory,
        target_id=factory.SelfAttribute("..target.id"),
    )
    data = factory.django.FileField(data=b"test", filename="data.txt")
    extra_data = factory.Faker("text")
    data_product_type = "photometry"
    featured = False
