import factory
from django.utils import timezone
from goats_tom.models import (
    Download,
)
from .user import UserFactory


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
