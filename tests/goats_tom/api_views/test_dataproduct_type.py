from django.conf import settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from tom_dataproducts.models import ReducedDatum

from goats_tom.api_views import DataProductTypeViewSet
from goats_tom.tests.factories import (
    DataProductFactory,
    ReducedDatumFactory,
    UserFactory,
)


class DataProductTypeViewSetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.data_product = DataProductFactory(data_product_type="fits_file")

        # GOATS runs with TARGET_PERMISSIONS_ONLY = False, under which
        # `DataProductTypeViewSet.get_queryset` restricts to data products the
        # user holds an explicit `view_dataproduct` permission on, rather than
        # inheriting visibility from the target. Granting it here is what the
        # real upload path does (see
        # `goats_tom.views.dataproduct_upload`); without it the viewset
        # correctly returns 404, which is the behaviour being relied on
        # elsewhere to keep one team's data products out of another's view.
        if not settings.TARGET_PERMISSIONS_ONLY:
            assign_perm(
                "tom_dataproducts.view_dataproduct", cls.user, cls.data_product
            )

    def _grant_view(self, data_product):
        """Grant the test user permission to view `data_product`.

        Needed for any data product created inside a test method, for the
        same reason as the one in `setUpTestData` -- see the comment there.
        """
        if not settings.TARGET_PERMISSIONS_ONLY:
            assign_perm(
                "tom_dataproducts.view_dataproduct", self.user, data_product
            )

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

    def test_partial_update_from_photometry_deletes_reduced_datum(self):
        """Retagging away from photometry deletes its ReducedDatum points."""
        data_product = DataProductFactory(data_product_type="photometry")
        self._grant_view(data_product)
        reduced_datum = ReducedDatumFactory(
            data_product=data_product, data_type="photometry"
        )
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "spectroscopy"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ReducedDatum.objects.filter(pk=reduced_datum.pk).exists()
        )

    def test_partial_update_keeps_reduced_datum_when_new_type_is_photometry(self):
        """Retagging into photometry doesn't delete existing ReducedDatum."""
        data_product = DataProductFactory(data_product_type="fits_file")
        self._grant_view(data_product)
        reduced_datum = ReducedDatumFactory(
            data_product=data_product, data_type="photometry"
        )
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "photometry"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(ReducedDatum.objects.filter(pk=reduced_datum.pk).exists())

    def test_partial_update_keeps_other_data_products_reduced_datum(self):
        """Retagging one data product doesn't touch another's ReducedDatum."""
        data_product = DataProductFactory(data_product_type="photometry")
        self._grant_view(data_product)
        other_data_product = DataProductFactory(data_product_type="photometry")
        self._grant_view(other_data_product)
        other_reduced_datum = ReducedDatumFactory(
            data_product=other_data_product, data_type="photometry"
        )
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "spectroscopy"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            ReducedDatum.objects.filter(pk=other_reduced_datum.pk).exists()
        )

    def test_partial_update_queues_success_message(self):
        """A successful retag queues a confirmation shown on the next render."""
        view = DataProductTypeViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/api/dataproducttype/",
            {"data_product_type": "spectroscopy"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        # APIRequestFactory skips MessageMiddleware; attach a storage manually.
        request.session = "session"
        request._messages = FallbackStorage(request)

        response = view(request, pk=self.data_product.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stored = [str(message) for message in request._messages]
        self.assertEqual(stored, ['Type changed to "Spectroscopy".'])

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
