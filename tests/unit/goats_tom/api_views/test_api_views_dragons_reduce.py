"""Test module for DRAGONS reductions."""

from unittest.mock import patch

from django.urls import reverse
from goats_tom.models import DRAGONSReduce
from goats_tom.tests.factories import (
    DRAGONSRecipeFactory,
    DRAGONSReduceFactory,
    DRAGONSRunFactory,
    UserFactory,
)
from goats_tom.api_views import DRAGONSReduceViewSet
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate


class TestDRAGONSReduceViewSet(APITestCase):
    """Class to test the `DRAGONSReduce` API view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = UserFactory()
        self.create_view = DRAGONSReduceViewSet.as_view({"post": "create"})
        self.list_view = DRAGONSReduceViewSet.as_view({"get": "list"})
        self.detail_view = DRAGONSReduceViewSet.as_view({"get": "retrieve"})
        self.partial_update_view = DRAGONSReduceViewSet.as_view(
            {"patch": "partial_update"},
        )

    def authenticate(self, request):
        """Helper method to authenticate requests."""
        force_authenticate(request, user=self.user)

    @patch("goats_tom.api_views.dragons_reduce.run_dragons_reduce.send")
    def test_create_reduction(self, mock_run_dragons_reduce):
        """Test creating a new DRAGONS reduction."""
        mock_run_dragons_reduce.return_value.message_id = "12345"
        recipe = DRAGONSRecipeFactory()
        data = {
            "recipe_id": recipe.id,
        }

        request = self.factory.post(reverse("dragonsreduce-list"), data)
        self.authenticate(request)

        response = self.create_view(request)

        # Check that the mock was called once
        mock_run_dragons_reduce.assert_called_once()

        assert response.status_code == status.HTTP_201_CREATED
        assert DRAGONSReduce.objects.count() == 1
        reduce = DRAGONSReduce.objects.first()
        self.assertEqual(reduce.task_id, "12345")

    def test_list_reductions(self):
        """Test listing all DRAGONS reductions."""
        DRAGONSReduceFactory.create_batch(3)

        request = self.factory.get(reverse("dragonsreduce-list"))
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 3

    def test_retrieve_reduction(self):
        """Test retrieving a single DRAGONS reduction."""
        reduction = DRAGONSReduceFactory()

        request = self.factory.get(reverse("dragonsreduce-detail", args=[reduction.id]))
        self.authenticate(request)

        response = self.detail_view(request, pk=reduction.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == reduction.id

    def test_invalid_create_reduction(self):
        """Test creating a DRAGONS reduction with invalid recipe."""
        data = {"recipe_id": 9999}

        request = self.factory.post(reverse("dragonsreduce-list"), data, format="json")
        self.authenticate(request)

        response = self.create_view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("goats_tom.api_views.dragons_reduce.abort")
    @patch("goats_tom.api_views.dragons_reduce.DRAGONSProgress.create_and_send")
    @patch("goats_tom.api_views.dragons_reduce.NotificationInstance.create_and_send")
    def test_valid_update_reduction(
        self, mock_notification_send, mock_progress_send, mock_abort,
    ):
        """Test valid updating of a DRAGONSReduce to 'canceled' status."""
        reduction = DRAGONSReduceFactory(task_id="12345")
        reduction.mark_initializing()
        data = {"status": "canceled"}

        request = self.factory.patch(
            reverse("dragonsreduce-detail", args=[reduction.id]), data,
        )
        self.authenticate(request)

        response = self.partial_update_view(request, pk=reduction.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reduction.refresh_from_db()
        mock_abort.assert_called_once_with(reduction.task_id)
        mock_progress_send.assert_called_once_with(reduction)
        mock_notification_send.assert_called_once_with(
            label=reduction.get_label(),
            color="warning",
            message="Background task canceled.",
        )
        self.assertEqual(reduction.status, "canceled")

    @patch("goats_tom.api_views.dragons_reduce.abort")
    @patch("goats_tom.api_views.dragons_reduce.DRAGONSProgress.create_and_send")
    @patch("goats_tom.api_views.dragons_reduce.NotificationInstance.create_and_send")
    def test_invalid_update_reduction(
        self, mock_notification_send, mock_progress_send, mock_abort,
    ):
        """Test invalid updating of a DRAGONSReduce with an unsupported status."""
        reduction = DRAGONSReduceFactory(status="running")
        data = {"status": "running"}

        request = self.factory.patch(
            reverse("dragonsreduce-detail", args=[reduction.id]), data,
        )
        self.authenticate(request)

        response = self.partial_update_view(request, pk=reduction.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reduction.refresh_from_db()
        self.assertEqual(reduction.status, "running")  # Status remains unchanged

        mock_abort.assert_not_called()
        mock_progress_send.assert_not_called()
        mock_notification_send.assert_not_called()

    def test_filter_by_run(self):
        """Test filtering DRAGONS reduces by run."""
        dragons_run = DRAGONSRunFactory()
        DRAGONSReduceFactory.create_batch(2, recipe__dragons_run=dragons_run)
        DRAGONSReduceFactory.create_batch(3)

        request = self.factory.get(
            reverse("dragonsreduce-list"), {"run": dragons_run.pk},
        )
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 2

    def test_filter_by_status(self):
        """Test filtering DRAGONS reduces by status."""
        status_filter = "running"
        DRAGONSReduceFactory.create_batch(2, status=status_filter)
        DRAGONSReduceFactory.create_batch(3)

        request = self.factory.get(
            reverse("dragonsreduce-list"), {"status": status_filter},
        )
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 2

    def test_filter_not_finished(self):
        """Test filtering DRAGONS reduces by not finished status."""
        DRAGONSReduceFactory.create_batch(2, status="running")
        DRAGONSReduceFactory.create_batch(1, status="done")
        DRAGONSReduceFactory.create_batch(1, status="canceled")
        DRAGONSReduceFactory.create_batch(1, status="error")

        request = self.factory.get(
            reverse("dragonsreduce-list"), {"not_finished": "true"},
        )
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 2

    def test_authentication_required(self):
        """Test that authentication is required to access the view."""
        request = self.factory.get(reverse("dragonsreduce-list"))

        response = self.list_view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
