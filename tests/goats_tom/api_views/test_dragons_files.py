"""Test module for a DRAGONS file."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from goats_tom.api_views import DRAGONSFilesViewSet
from goats_tom.tests.factories import DRAGONSFileFactory, DRAGONSRunFactory, UserFactory


class TestDRAGONSFilesViewSet(APITestCase):
    """Class to test the `DRAGONSFile` API view."""
    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.list_view = DRAGONSFilesViewSet.as_view({"get": "list"})
        cls.detail_view = DRAGONSFilesViewSet.as_view({"get": "retrieve"})
        cls.update_view = DRAGONSFilesViewSet.as_view({"patch": "partial_update"})

    def authenticate(self, request):
        """Helper method to authenticate requests."""
        force_authenticate(request, user=self.user)

    def test_list_files(self):
        """Test listing all DRAGONS files."""
        DRAGONSFileFactory.create_batch(3)

        request = self.factory.get(reverse("dragonsfiles-list"))
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 3

    def test_retrieve_file(self):
        """Test retrieving a single DRAGONS file."""
        dragons_file = DRAGONSFileFactory()

        request = self.factory.get(
            reverse("dragonsfiles-detail", args=[dragons_file.id]),
        )
        self.authenticate(request)

        response = self.detail_view(request, pk=dragons_file.id)

        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_dragons_run(self):
        """Test filtering DRAGONS files by DRAGONS run."""
        dragons_run = DRAGONSRunFactory()
        DRAGONSFileFactory.create_batch(2, dragons_run=dragons_run)
        DRAGONSFileFactory.create_batch(3)

        request = self.factory.get(
            reverse("dragonsfiles-list"), {"dragons_run": dragons_run.pk},
        )
        self.authenticate(request)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 2

    def test_authentication_required(self):
        """Test that authentication is required to access the view."""
        request = self.factory.get(reverse("dragonsfiles-list"))

        response = self.list_view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
