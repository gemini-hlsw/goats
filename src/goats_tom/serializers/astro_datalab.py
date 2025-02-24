"""Module to serialize/deserialize file to send to Astro Datalab."""

__all__ = ["AstroDatalabSerializer"]

from rest_framework import serializers
from tom_dataproducts.models import DataProduct


class AstroDatalabSerializer(serializers.Serializer):
    data_product = serializers.PrimaryKeyRelatedField(
        queryset=DataProduct.objects.all(),
        required=True,
        help_text="The ID of the DataProduct to send to Astro Datalab.",
    )
