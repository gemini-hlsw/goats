"""This module contains factory classes for creating instances of various models
used in the application, particularly for testing purposes.
"""

import factory
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.utils import timezone
from goats_tom.models import (
    BaseRecipe,
    Download,
    DRAGONSFile,
    DRAGONSRecipe,
    DRAGONSReduce,
    DRAGONSRun,
    GOALogin,
    AstroDatalabLogin,
    Key,
    ProgramKey,
    UserKey,
    RecipesModule
)
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory
from datetime import datetime, timedelta
import random
import uuid


class UserFactory(factory.django.DjangoModelFactory):
    """Factory class for creating `User` model instances for testing.

    Attributes
    ----------
    username : factory.Sequence
        Generates a unique username sequence for each user instance.
    password : str
        A hashed password, generated using `make_password` for consistency in
        tests.

    """

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    password = make_password("password")


class DownloadFactory(factory.django.DjangoModelFactory):
    # Factory for creating TaskProgress instances for testing.
    class Meta:
        model = Download

    observation_id = "GN-2024A-Q-1-1"
    unique_id = factory.Faker("uuid4")
    status = "running"
    done = False
    start_time = factory.LazyFunction(timezone.now)
    end_time = None
    user = factory.SubFactory(UserFactory)
    num_files_downloaded = 1
    num_files_omitted = 2


class DataProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DataProduct

    product_id = factory.LazyAttribute(
        lambda o: f"{o.target.name}__{o.observation_record.observation_id}__{uuid.uuid4()}"
    )
    target = factory.SubFactory(SiderealTargetFactory)
    # Ensure observation_record is associated with the same target as
    # DataProduct
    observation_record = factory.SubFactory(
        ObservingRecordFactory, target_id=factory.SelfAttribute("..target.id"),
    )
    data = factory.django.FileField(data=b"test", filename="data.txt")
    extra_data = factory.Faker("text")
    data_product_type = "photometry"
    featured = False



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


class KeyFactory(factory.django.DjangoModelFactory):
    """Base factory for keys."""

    class Meta:
        model = Key
        abstract = True

    user = factory.SubFactory(UserFactory)
    password = "default_password"
    site = factory.Iterator(["GS", "GN"])


class UserKeyFactory(KeyFactory):
    """Factory for UserKey model."""

    class Meta:
        model = UserKey

    email = factory.LazyAttribute(lambda obj: f"{obj.user.username}@example.com")
    is_active = False


class ProgramKeyFactory(KeyFactory):
    """Factory for ProgramKey model."""

    class Meta:
        model = ProgramKey

    program_id = factory.Sequence(lambda n: f"GN-2024A-Q-{n}")

    @factory.lazy_attribute
    def site(self):
        """Determine the site based on the program_id."""
        return self.program_id.split("-")[0]


class DRAGONSRunFactory(factory.django.DjangoModelFactory):
    """Factory for creating DRAGONSRun instances for testing."""

    class Meta:
        model = DRAGONSRun

    observation_record = factory.SubFactory(ObservingRecordFactory, target_id=1)
    run_id = factory.Faker("uuid4")
    config_filename = "dragonsrc"
    output_directory = factory.Faker("file_path")
    cal_manager_filename = "cal_manager.db"
    log_filename = "log.log"


class RecipesModuleFactory(factory.django.DjangoModelFactory):
    """Factory for creating `RecipesModule` instances for testing."""

    class Meta:
        model = RecipesModule

    name = factory.Faker("word")
    version = factory.Faker("numerify", text='#.#.#')
    instrument = factory.Faker("word")

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
    astrodata_descriptors = factory.LazyAttribute(lambda x: {
        "airmass": random.uniform(1.0, 3.0),
        "binning": f"{random.choice([1, 2])}x{random.choice([1, 2])}",
        "central_wavelength": random.uniform(350.0, 2500.0),
        "exposure_time": random.uniform(0.1, 3600.0),
        "ut_date": (datetime.now() - timedelta(days=random.randint(0, 365))).date().isoformat(),
        "ut_datetime": datetime.now().isoformat(),
        "local_time": (datetime.now() - timedelta(hours=random.randint(1, 12))).time().isoformat(),
        "ut_time": datetime.now().time().isoformat()
    })
    url = factory.Faker("url")
    product_id = factory.SelfAttribute("data_product.product_id")

class BaseRecipeFactory(factory.django.DjangoModelFactory):
    """Factory for creating `BaseRecipe` instances for testing."""

    class Meta:
        model = BaseRecipe

    name = factory.Sequence(lambda n: f"Recipe{n}")
    function_definition = factory.Faker("paragraph")
    recipes_module = factory.SubFactory(RecipesModuleFactory)


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


class _BaseLoginFactory(factory.django.DjangoModelFactory):
    """Abstract factory for BaseLogin subclasses."""
    user = factory.SubFactory(UserFactory)
    username = factory.Faker("user_name")
    password = factory.Faker(
        "password",
        length=12,
        special_chars=True,
        digits=True,
        upper_case=True,
        lower_case=True,
    )

    class Meta:
        abstract = True


class GOALoginFactory(_BaseLoginFactory):
    """Factory for GOALogin."""
    class Meta:
        model = GOALogin


class AstroDatalabLoginFactory(_BaseLoginFactory):
    """Factory for AstroDatalabLogin."""
    class Meta:
        model = AstroDatalabLogin
