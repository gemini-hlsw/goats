"""Module providing filtering capabilities for `ReducedDatum` objects."""

__all__ = ["ReducedDatumFilter"]

from django_filters import rest_framework as filters
from tom_dataproducts.models import DataProduct, ReducedDatum


class ReducedDatumFilter(filters.FilterSet):
    """FilterSet for `ReducedDatum` objects."""

    data_product = filters.ModelChoiceFilter(queryset=DataProduct.objects.all())
    data_type = filters.CharFilter(field_name="data_type", lookup_expr="exact")

    class Meta:
        model = ReducedDatum
        fields = ["data_product", "data_type"]
