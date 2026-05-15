"""Tests for the DRAGONS DataProductsViewSet override.

This module tests ``goats_tom.api_views.DataProductsViewSet``, which overrides
TOMToolkit's ``DataProductViewSet`` to support DRAGONS-specific data product
management. The override adds a ``file_status`` field to the create endpoint
so that existing DataProducts produced by a DRAGONS run can be re-processed
without creating a new record (``file_status == "updated"``).

The TOMToolkit base class logic (``CreateModelMixin.create``) is stubbed out
in the ``"new"`` tests — we are only exercising our own override code, not the
framework's serialization and persistence layer.
"""

from unittest.mock import ANY, MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from tom_dataproducts.models import ReducedDatum

from goats_tom.api_views import DataProductsViewSet
from goats_tom.models import DataProductMetadata
from goats_tom.tests.factories import DataProductFactory, UserFactory

MODULE = "goats_tom.api_views.dataproducts"


def _stub_mixin_create(dp_id, http_status=201, groups=None):
    """Return a stub for ``CreateModelMixin.create`` used in 'new' file tests.

    Replaces the TOMToolkit mixin so tests only exercise the DRAGONS override
    logic that runs after the mixin returns a successful response.
    """
    def stub(self, request, *args, **kwargs):
        return Response({"id": dp_id, "group": groups or []}, status=http_status)

    return stub


class TestDRAGONSDataProductsViewSetNew(APITestCase):
    """Tests for the ``file_status == 'new'`` branch.

    The mixin call (``CreateModelMixin.create``) is stubbed so these tests
    focus exclusively on the DRAGONS post-creation logic: metadata creation,
    hook execution, data processing, and rollback on failure.
    """

    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.view = DataProductsViewSet.as_view({"post": "create"})

    def _post(self, data):
        request = self.factory.post(
            reverse("dragonsdataproducts-list"), data, format="json"
        )
        force_authenticate(request, user=self.user)
        return self.view(request)

    @patch(f"{MODULE}.run_hook")
    @patch(f"{MODULE}.run_data_processor")
    def test_new_file_creates_metadata_and_returns_201(self, mock_processor, mock_hook):
        """Successful upload creates DataProductMetadata and triggers processing.

        The view re-fetches the DataProduct from the DB after the mixin call, so
        the dp object inside the view is a different Python instance than the one
        from the factory. We use ANY to verify the calls were made without
        requiring object identity, and check the DB directly for the metadata.
        """
        dp = DataProductFactory()

        with patch(f"{MODULE}.CreateModelMixin.create", _stub_mixin_create(dp.id)):
            response = self._post({"file_status": "new"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Data product successfully uploaded.")
        self.assertTrue(DataProductMetadata.objects.filter(dataproduct=dp, processed=True).exists())
        mock_hook.assert_called_once_with("data_product_post_upload", ANY)
        mock_processor.assert_called_once_with(ANY)

    @patch(f"{MODULE}.run_data_processor")
    @patch(f"{MODULE}.run_hook")
    @patch(f"{MODULE}.DataProductMetadata.objects.create")
    def test_new_file_processing_error_deletes_dp_and_returns_500(
        self, mock_meta_create, mock_hook, mock_processor
    ):
        """Processing failure deletes the DataProduct and its ReducedDatums."""
        from tom_dataproducts.models import DataProduct as DP

        dp = DataProductFactory()
        dp_id = dp.id
        mock_processor.side_effect = Exception("processing failed")

        with patch(f"{MODULE}.CreateModelMixin.create", _stub_mixin_create(dp_id)):
            response = self._post({"file_status": "new"})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        self.assertFalse(DP.objects.filter(pk=dp_id).exists())

    def test_new_file_mixin_non_201_is_passed_through(self):
        """Non-201 response from the mixin is returned to the caller unchanged."""
        with patch(
            f"{MODULE}.CreateModelMixin.create",
            _stub_mixin_create(None, http_status=400),
        ):
            response = self._post({"file_status": "new"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDRAGONSDataProductsViewSetUpdated(APITestCase):
    """Tests for the ``file_status == 'updated'`` branch.

    This is the core of GOATS-1302: when DRAGONS re-runs a reduction and
    produces a file with the same name, the existing DataProduct is located by
    ``product_id``, its ReducedDatums are cleared, and it is re-processed.
    """

    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.view = DataProductsViewSet.as_view({"post": "create"})

    def _post(self, data):
        request = self.factory.post(
            reverse("dragonsdataproducts-list"), data, format="json"
        )
        force_authenticate(request, user=self.user)
        return self.view(request)

    @patch(f"{MODULE}.run_hook")
    @patch(f"{MODULE}.run_data_processor")
    def test_updated_file_returns_200_and_reprocesses(self, mock_processor, mock_hook):
        """Updating a DRAGONS DataProduct clears ReducedDatums and reprocesses."""
        dp = DataProductFactory()

        response = self._post({"file_status": "updated", "productId": dp.product_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Data product successfully updated.")
        mock_hook.assert_called_once_with("data_product_post_upload", dp)
        mock_processor.assert_called_once_with(dp)

    @patch(f"{MODULE}.run_hook")
    @patch(f"{MODULE}.run_data_processor")
    def test_updated_file_with_last_modified_succeeds(self, mock_processor, mock_hook):
        """Providing last_modified alongside productId does not break the update."""
        dp = DataProductFactory()

        response = self._post({
            "file_status": "updated",
            "productId": dp.product_id,
            "last_modified": "2025-01-15T12:00:00Z",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_updated_file_not_found_returns_404(self):
        """Returns 404 when no DataProduct matches the given productId."""
        response = self._post({
            "file_status": "updated",
            "productId": "nonexistent/dragons/output.fits",
        })

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    @patch(f"{MODULE}.run_data_processor")
    @patch(f"{MODULE}.run_hook")
    def test_updated_file_processing_error_returns_500_and_cleans_up(
        self, mock_hook, mock_processor
    ):
        """Processing failure returns 500 and removes leftover ReducedDatums."""
        dp = DataProductFactory()
        mock_processor.side_effect = Exception("processing failed")

        response = self._post({"file_status": "updated", "productId": dp.product_id})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        self.assertFalse(ReducedDatum.objects.filter(data_product=dp).exists())


class TestDRAGONSDataProductsViewSetInvalidStatus(APITestCase):
    """Tests for missing or unrecognized file_status values."""

    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls.user = UserFactory()
        cls.view = DataProductsViewSet.as_view({"post": "create"})

    def _post(self, data):
        request = self.factory.post(
            reverse("dragonsdataproducts-list"), data, format="json"
        )
        force_authenticate(request, user=self.user)
        return self.view(request)

    def test_invalid_file_status_returns_400(self):
        """An unrecognized file_status returns 400."""
        response = self._post({"file_status": "unknown"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_missing_file_status_returns_400(self):
        """Omitting file_status returns 400."""
        response = self._post({})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_none_file_status_returns_400(self):
        """Explicitly passing None as file_status returns 400."""
        request = self.factory.post(
            reverse("dragonsdataproducts-list"),
            {"file_status": None},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
