from rest_framework.test import APITestCase
from tom_dataproducts.api_views import ReducedDatumViewSet as BaseReducedDatumViewSet

from goats_tom.api_views import ReducedDatumViewSet
from goats_tom.filters import ReducedDatumFilter


class TestReducedDatumViewSet(APITestCase):
    def test_inherits_from_base(self):
        """Test that ReducedDatumViewSet inherits from the base viewset."""
        self.assertTrue(issubclass(ReducedDatumViewSet, BaseReducedDatumViewSet))

    def test_filterset_class_is_correct(self):
        """Test that ReducedDatumViewSet specifies the correct filterset class."""
        self.assertEqual(ReducedDatumViewSet.filterset_class, ReducedDatumFilter)
