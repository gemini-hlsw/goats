import random
from datetime import datetime, timedelta

import factory

from goats_tom.models import (
    DRAGONSFile,
)

from .dataproduct import DataProductFactory
from .dragons_run import DRAGONSRunFactory
from .recipes_module import RecipesModuleFactory


class DRAGONSFileFactory(factory.django.DjangoModelFactory):
    """Factory for `DRAGONSFile`."""

    class Meta:
        model = DRAGONSFile

    dragons_run = factory.SubFactory(DRAGONSRunFactory)
    data_product = factory.SubFactory(DataProductFactory)
    recipes_module = factory.SubFactory(RecipesModuleFactory)
    observation_type = factory.Iterator(["bias", "flat", "object", "arc"])
    observation_class = factory.Iterator(["partnerCal", "science"])
    object_name = factory.Faker("word")
    astrodata_descriptors = factory.LazyAttribute(
        lambda x: {
            "airmass": random.uniform(1.0, 3.0),
            "binning": f"{random.choice([1, 2])}x{random.choice([1, 2])}",
            "central_wavelength": random.uniform(350.0, 2500.0),
            "exposure_time": random.uniform(0.1, 3600.0),
            "ut_date": (datetime.now() - timedelta(days=random.randint(0, 365)))
            .date()
            .isoformat(),
            "ut_datetime": datetime.now().isoformat(),
            "local_time": (datetime.now() - timedelta(hours=random.randint(1, 12)))
            .time()
            .isoformat(),
            "ut_time": datetime.now().time().isoformat(),
        }
    )
    url = factory.Faker("url")
    product_id = factory.SelfAttribute("data_product.product_id")
