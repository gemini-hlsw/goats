"""Test module for a DRAGONS run."""

from django.urls import reverse
from goats_tom.models import DRAGONSRun
from goats_tom.tests.factories import DRAGONSRunFactory, UserFactory
from goats_tom.api_views import DRAGONSRunsViewSet
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


class TestDRAGONSRunViewSet(APITestCase):
    """Class to test the `DRAGONSRun` API View."""

    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.list_view = DRAGONSRunsViewSet.as_view({"get": "list", "post": "create"})
        cls.detail_view = DRAGONSRunsViewSet.as_view(
            {"get": "retrieve", "delete": "destroy"},
        )

    def authenticate(self, request):
        """Helper method to authenticate requests."""
        force_authenticate(request, user=self.user)

    def test_list_runs(self):
        """Test listing all DRAGONS runs."""
        DRAGONSRunFactory.create_batch(3)

        request = self.factory.get(reverse("dragonsruns-list"))
        self.authenticate(request)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 3)

    def test_create_run(self):
        """Test creating a new DRAGONS run."""
        target = SiderealTargetFactory.create()
        observation_record = ObservingRecordFactory.create(target_id=target.id)
        data = {
            "observation_record": observation_record.id,
            "run_id": "test-run",
            "config_filename": "test-config",
            "output_directory": "output",
            "cal_manager_filename": "test-cal-manager.db",
            "log_filename": "test-log.log",
        }

        request = self.factory.post(reverse("dragonsruns-list"), data, format="json")
        self.authenticate(request)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DRAGONSRun.objects.count(), 1)
        self.assertEqual(DRAGONSRun.objects.get().run_id, "test-run")

    def test_retrieve_run(self):
        """Test retrieving a single DRAGONS run."""
        dragons_run = DRAGONSRunFactory()

        request = self.factory.get(reverse("dragonsruns-detail", args=[dragons_run.id]))
        self.authenticate(request)

        response = self.detail_view(request, pk=dragons_run.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["run_id"], dragons_run.run_id)

    def test_delete_run(self):
        """Test deleting a DRAGONS run."""
        dragons_run = DRAGONSRunFactory()

        request = self.factory.delete(
            reverse("dragonsruns-detail", args=[dragons_run.id]),
        )
        self.authenticate(request)

        response = self.detail_view(request, pk=dragons_run.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DRAGONSRun.objects.count(), 0)

    def test_filter_by_observation_record(self):
        """Test filtering DRAGONS runs by observation record."""
        target = SiderealTargetFactory.create()
        observation_record = ObservingRecordFactory.create(target_id=target.id)
        DRAGONSRunFactory.create_batch(2, observation_record=observation_record)
        DRAGONSRunFactory.create_batch(3)

        request = self.factory.get(
            reverse("dragonsruns-list"), {"observation_record": observation_record.pk},
        )
        self.authenticate(request)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results")), 2)

    def test_invalid_create_run(self):
        """Test creating a DRAGONS run with invalid data."""
        data = {
            "observation_record": None,
            "run_id": "test-run",
            "config_filename": "test-config",
            "output_directory": "output",
            "cal_manager_filename": "test-cal-manager.db",
            "log_filename": "test-log.log",
        }

        request = self.factory.post(reverse("dragonsruns-list"), data, format="json")
        self.authenticate(request)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authentication_required(self):
        """Test that authentication is required to access the view."""
        request = self.factory.get(reverse("dragonsruns-list"))

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
