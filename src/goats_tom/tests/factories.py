"""
This module contains factory classes for creating instances of various models
used in the application, particularly for testing purposes.
"""

import factory
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from goats_tom.models import (
    DataProductMetadata,
    Download,
    DRAGONSFile,
    DRAGONSRecipe,
    DRAGONSRun,
    GOALogin,
    Key,
    ProgramKey,
    UserKey,
)
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


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


class GOALoginFactory(factory.django.DjangoModelFactory):
    """Factory for creating GOALogin instances for testing."""

    class Meta:
        model = GOALogin
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    username = factory.Sequence(lambda n: f"testuser{n}")
    password = "default_password"


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

    product_id = factory.Faker("uuid4")
    target = factory.SubFactory(SiderealTargetFactory)
    # Ensure observation_record is associated with the same target as
    # DataProduct
    observation_record = factory.SubFactory(
        ObservingRecordFactory, target_id=factory.SelfAttribute("..target.id")
    )
    data = ContentFile(b"some data", name="data.txt")
    extra_data = factory.Faker("text")
    data_product_type = "photometry"
    featured = False

    @factory.post_generation
    def create_metadata(self, create, extracted, **kwargs):
        if create and extracted and not hasattr(self, "metadata"):
            DataProductMetadataFactory(data_product=self)


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
        lambda: {"magnitude": 15.582, "filter": "r", "error": 0.005}
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
    run_id = ""
    config_filename = "dragonsrc"
    output_directory = ""
    cal_manager_filename = "cal_manager.db"
    log_filename = "log.log"


class DataProductMetadataFactory(factory.django.DjangoModelFactory):
    """Factory for `DataProductMetadata`."""

    class Meta:
        """Configuration."""

        model = DataProductMetadata

    data_product = factory.SubFactory(DataProductFactory)
    file_type = factory.Faker("word")
    group_id = factory.Faker("word")
    exposure_time = factory.Faker("pyfloat", positive=True)
    object_name = factory.Faker("word")
    central_wavelength = factory.Faker("pyfloat", positive=True)
    wavelength_band = factory.Faker("word")
    observation_date = factory.Faker("date")
    roi_setting = factory.Faker("word")


class DRAGONSFileFactory(factory.django.DjangoModelFactory):
    """Factory for `DRAGONSFile`."""

    class Meta:
        """Configuration."""

        model = DRAGONSFile

    dragons_run = factory.SubFactory(DRAGONSRunFactory)
    data_product = factory.SubFactory(DataProductFactory, create_metadata=True)
    enabled = factory.Faker("boolean")


class DRAGONSRecipeFactory(factory.django.DjangoModelFactory):
    """Factory for `DRAGONSRecipe`."""

    class Meta:
        """Configuration."""

        model = DRAGONSRecipe

    dragons_run = factory.SubFactory(DRAGONSRunFactory)
    file_type = factory.Faker("word")
    name = factory.Faker("sentence")
    function_definition = factory.Faker("text")
