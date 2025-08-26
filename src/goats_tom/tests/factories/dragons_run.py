import factory
from tom_observations.tests.factories import ObservingRecordFactory

from goats_tom.models import (
    DRAGONSRun,
)


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
    created = None
    modified = None
    version = factory.Faker("numerify", text="3.0.#")
