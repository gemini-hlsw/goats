from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import AstroDatalabViewSet
from goats_tom.tests.factories import DataProductFactory, UserFactory


class AstroDatalabViewSetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.data_product = DataProductFactory()

    @patch.object(AstroDatalabViewSet, "send_to_astro_datalab")
    def test_create_calls_send_to_astro_datalab(self, mock_send_to_astro_datalab):
        """Test that create() calls send_to_astro_datalab with the correct arguments."""
        view = AstroDatalabViewSet.as_view({"post": "create"})
        request = self.factory.post(
            "/astro-datalab/", {"data_product": self.data_product.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_send_to_astro_datalab.assert_called_once_with(self.user, self.data_product)

    @patch.object(AstroDatalabViewSet, "send_to_astro_datalab", side_effect=Exception("Upload failed"))
    def test_create_handles_send_to_astro_datalab_exception(self, mock_send_to_astro_datalab):
        """Test handle exceptions from send_to_astro_datalab gracefully."""
        view = AstroDatalabViewSet.as_view({"post": "create"})
        request = self.factory.post(
            "/astro-datalab/", {"data_product": self.data_product.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Upload failed")
