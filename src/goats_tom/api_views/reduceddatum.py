"""Module overriding the `filterset_class` to allow us to filter results."""

from tom_dataproducts.api_views import ReducedDatumViewSet as BaseReducedDatumViewSet

from goats_tom.filters import ReducedDatumFilter


class ReducedDatumViewSet(BaseReducedDatumViewSet):
    filterset_class = ReducedDatumFilter

    def get_queryset(self):
        """Return the reduced datums newest first."""
        return super().get_queryset().order_by("-timestamp", "-pk")
