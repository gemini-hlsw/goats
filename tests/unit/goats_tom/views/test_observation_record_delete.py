import pytest
from unittest.mock import MagicMock
from django.http import HttpRequest, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from goats_tom.tests.factories import (
    DataProductFactory,
    UserFactory,
)
from goats_tom.views import (
    ObservationRecordDeleteView,
)
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory


class TestObservationRecordDeleteView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

        # Create an ObservationRecord and associated DataProducts.
        # Manually create a Target instance.
        self.target = SiderealTargetFactory.create()

        # Create an ObservationRecord with the created Target.
        self.observation_record = ObservingRecordFactory.create(
            target_id=self.target.id,
        )
        DataProductFactory(observation_record=self.observation_record)

    def test_form_valid(self):
        # Ensure the ObservationRecord and DataProducts exist.
        self.assertIsNotNone(
            ObservationRecord.objects.filter(pk=self.observation_record.pk).first(),
        )
        self.assertEqual(
            DataProduct.objects.filter(
                observation_record=self.observation_record,
            ).count(),
            1,
        )

        # Setup the request and view.
        request = HttpRequest()
        request.user = self.user
        view = ObservationRecordDeleteView()
        view.request = request
        view.kwargs = {"pk": self.observation_record.pk}
        view.object = self.observation_record

        # Call the form_valid method
        response = view.form_valid(form=MagicMock())

        # Test that the ObservationRecord is deleted.
        with pytest.raises(ObservationRecord.DoesNotExist):
            ObservationRecord.objects.get(pk=self.observation_record.pk)

        # Test that associated DataProducts are deleted
        self.assertEqual(
            DataProduct.objects.filter(
                observation_record=self.observation_record,
            ).count(),
            0,
        )

        # Test redirection to the success URL.
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, reverse("observations:list"))
