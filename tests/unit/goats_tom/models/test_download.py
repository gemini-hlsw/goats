from datetime import timedelta
from goats_tom.models import Download
import pytest
from django.test import TestCase
from django.utils import timezone
from goats_tom.tests.factories import (
    DownloadFactory,
)


@pytest.mark.django_db()
class TestDownloadModel(TestCase):
    def setUp(self):
        self.task = DownloadFactory()

    def test_immediate_task_completion(self):
        self.task.finish()
        assert self.task.total_time == "0s"

    def test_long_duration_task(self):
        self.task.start_time = timezone.now() - timedelta(
            days=1,
        )  # Simulate a long-running task
        self.task.finish()
        assert "1d" in self.task.total_time