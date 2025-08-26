from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from goats_tom.api_views import RunProcessorViewSet
from goats_tom.tests.factories import (
    DataProductFactory,
    ReducedDatumFactory,
    UserFactory,
)


class TestRunProcessorViewSet(APITestCase):
    """Class to test the `RunProcessorViewSet` API View."""

    def setUp(self):
        """Set up test environment."""
        self.factory = APIRequestFactory()
        self.user = UserFactory()
        self.view = RunProcessorViewSet.as_view({"post": "create"})

    def authenticate(self, request):
        """Helper method to authenticate requests."""
        force_authenticate(request, user=self.user)

    @patch("goats_tom.api_views.run_processor.run_data_processor")
    def test_create_successful_processing(self, mock_run_data_processor):
        """Test successful processing of a data product."""
        data_product = DataProductFactory()
        mock_reduced_data = [ReducedDatumFactory(data_product=data_product, target=data_product.target)]
        mock_run_data_processor.return_value = mock_reduced_data

        payload = {
            "data_product": data_product.id,
            "data_product_type": "photometry",
        }

        request = self.factory.post(reverse("runprocessor-list"), payload, format="json")
        self.authenticate(request)

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), len(mock_reduced_data))
        mock_run_data_processor.assert_called_once_with(data_product, "photometry")

    @patch("goats_tom.api_views.run_processor.run_data_processor")
    def test_create_processing_error(self, mock_run_data_processor):
        """Test processing error handling."""
        data_product = DataProductFactory()
        mock_run_data_processor.side_effect = Exception("Processing failed")

        payload = {
            "data_product": data_product.id,
            "data_product_type": "photometry",
        }

        request = self.factory.post(reverse("runprocessor-list"), payload, format="json")
        self.authenticate(request)

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Processing failed")
        mock_run_data_processor.assert_called_once_with(data_product, "photometry")

    def test_create_unauthenticated(self):
        """Test that unauthenticated requests return 401."""
        data_product = DataProductFactory()

        payload = {
            "data_product": data_product.id,
            "data_product_type": "photometry",
        }

        request = self.factory.post(reverse("runprocessor-list"), payload, format="json")

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
