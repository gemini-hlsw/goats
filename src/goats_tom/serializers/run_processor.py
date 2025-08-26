"""Module for serialize/deserialize processor information."""

__all__ = ["RunProcessorSerializer"]

from django.conf import settings
from rest_framework import serializers
from tom_dataproducts.models import DataProduct

DATA_PRODUCT_TYPE_CHOICES = list(settings.DATA_PRODUCT_TYPES.keys())


class RunProcessorSerializer(serializers.Serializer):
    """Serializer for validating data required to run a data processor."""

    data_product = serializers.PrimaryKeyRelatedField(
        queryset=DataProduct.objects.all(),
        required=True,
        help_text="The ID of the DataProduct to process.",
    )
    data_product_type = serializers.ChoiceField(
        choices=DATA_PRODUCT_TYPE_CHOICES, required=True, allow_null=True
    )
