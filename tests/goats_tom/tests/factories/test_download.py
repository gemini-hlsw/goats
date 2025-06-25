import pytest
from django.utils import timezone

from goats_tom.tests.factories import (
    DownloadFactory,
)


@pytest.mark.django_db()
def test_task_progress_factory():
    # Test the TaskProgress factory.
    task = DownloadFactory.create()

    assert task.unique_id is not None
    assert task.status == "running"
    assert not task.done
    assert task.start_time <= timezone.now()
    assert task.end_time is None
    assert task.user is not None

    # Test the finish method.
    task.finish(message="Test error", error=True)
    assert task.status == "Failed"
    assert task.message == "Test error"
    task.done = True
    assert task.total_time != "N/A"
