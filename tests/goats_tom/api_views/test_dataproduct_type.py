from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import DataProductTypeViewSet
from goats_tom.tests.factories import DataProductFactory, UserFactory


class DataProductTypeViewSetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.data_product = DataProductFactory(data_product_type="fits_file")

    def test_partial_update_sets_data_product_type(self):
        """Test that a PATCH updates the `data_product_type`."""
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "spectroscopy"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=self.data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.data_product.refresh_from_db()
        self.assertEqual(self.data_product.data_product_type, "spectroscopy")

    def test_partial_update_rejects_invalid_type(self):
        """Test that an unknown `data_product_type` is rejected."""
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "not_a_real_type"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=self.data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.data_product.refresh_from_db()
        self.assertEqual(self.data_product.data_product_type, "fits_file")

    def test_partial_update_requires_authentication(self):
        """Test that an unauthenticated request is rejected."""
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "spectroscopy"},
            format="json",
        )

        response = view(request, pk=self.data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
