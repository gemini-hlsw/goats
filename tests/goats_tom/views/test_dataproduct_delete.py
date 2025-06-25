from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.http import HttpRequest, HttpResponseRedirect
from rest_framework.test import APITestCase
from tom_dataproducts.models import DataProduct, ReducedDatum

from goats_tom.tests.factories import (
    DataProductFactory,
    ReducedDatumFactory,
    UserFactory,
)
from goats_tom.views import (
    DataProductDeleteView,
)


class TestDataProductDeleteView(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

        # Use factories to create test objects.
        self.data_product = DataProductFactory.create()

        # Create associated ReducedDatum objects.
        ReducedDatumFactory(data_product=self.data_product)
        # Verify the number of ReducedDatum objects before deletion.
        initial_reduced_datum_count = ReducedDatum.objects.filter(
            data_product=self.data_product,
        ).count()
        self.assertEqual(
            initial_reduced_datum_count, 1, "Initial ReducedDatum count does not match",
        )

    def test_form_valid(self):
        # Setup the request and view.
        request = HttpRequest()
        view = DataProductDeleteView()
        view.request = request
        view.kwargs = {"pk": self.data_product.pk}
        view.object = self.data_product

        # Get the path of the associated file before deletion.
        file_path = Path(self.data_product.data.path)

        # Call the form_valid method.
        response = view.form_valid(form=MagicMock())

        # Test that the DataProduct is deleted.
        with pytest.raises(DataProduct.DoesNotExist):
            DataProduct.objects.get(pk=self.data_product.pk)

        # Test that associated ReducedDatum objects are deleted.
        self.assertEqual(
            ReducedDatum.objects.filter(data_product=self.data_product).count(), 0,
        )

        # Test that the file is deleted.
        self.assertFalse(file_path.exists(), "File was not deleted")

        # Test redirection to the success URL.
        self.assertIsInstance(response, HttpResponseRedirect)
