import json
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpRequest

from goats_tom.models import Download
from goats_tom.tests.factories import (
    DownloadFactory,
)
from goats_tom.views import (
    ongoing_tasks,
)


@pytest.fixture()
def mock_request():
    return HttpRequest()

class TestOngoingTasks:
    """Class to test the ongoing_tasks view."""

    @staticmethod
    def mock_queryset(*args, **kwargs):
        """Helper function to mock QuerySet behavior.

        Returns a MagicMock object that simulates Django's QuerySet.
        """
        mock = MagicMock(spec=Download.objects.none())
        mock.filter.return_value = mock
        mock.values.return_value = list(args) if args else []
        return mock

    @patch("goats_tom.views.tasks.Download")
    def test_ongoing_tasks_no_tasks(self, mock_task_progress, mock_request):
        """Test the ongoing_tasks view with no ongoing tasks."""
        mock_task_progress.objects.filter.return_value = self.mock_queryset()

        response = ongoing_tasks(mock_request)
        assert response.status_code == 200
        assert json.loads(response.content) == []

    @pytest.mark.django_db()
    @patch("goats_tom.views.tasks.Download")
    def test_ongoing_tasks_with_tasks(self, mock_task_progress, mock_request):
        """Test the ongoing_tasks view with some ongoing tasks."""
        test_tasks = [
            {"unique_id": task.unique_id, "status": task.status}
            for task in DownloadFactory.create_batch(2, status="running", done=False)
        ]
        mock_task_progress.objects.filter.return_value = self.mock_queryset(*test_tasks)

        response = ongoing_tasks(mock_request)
        assert response.status_code == 200
        assert json.loads(response.content) == test_tasks
