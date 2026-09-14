__all__ = ["DataProductListView"]

from tom_dataproducts.views import DataProductListView as BaseDataProductListView

from goats_tom.views.ordering import DateOrderingMixin


class DataProductListView(DateOrderingMixin, BaseDataProductListView):
    """Data product list, orderable by creation date via ``?order=``."""

    # Products saved together share a timestamp, so fall back to the file name.
    tiebreaker = "data"
