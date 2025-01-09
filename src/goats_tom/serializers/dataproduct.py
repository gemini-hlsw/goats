"""Module for overriding the serializer for data products in DRAGONS reductions.

This module extends the `DataProductSerializer` from the TOM Toolkit to handle cases
where the data product does not include a direct file upload but is instead specified
by a file path within the local system, specifically under settings.MEDIA_ROOT. This
adaptation is necessary to integrate with the DRAGONS run system, which generates
output without direct user file uploads.

The serializer adds fields for specifying the file path and associated DRAGONS run,
allowing the backend to link data products with their corresponding DRAGONS runs and
avoid the overhead of handling file uploads that are already managed by the system.

This custom serializer will only be used in DRAGONS reductions.
"""

__all__ = ["DataProductSerializer"]

from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers
from tom_dataproducts.serializers import (
    DataProductSerializer as BaseDataProductSerializer,
)

from goats_tom.models import DRAGONSRun


class DataProductSerializer(BaseDataProductSerializer):
    """Taken from TOMToolkit but had to override to handle not having a file."""

    filepath = serializers.CharField(write_only=True, required=True)
    filename = serializers.CharField(write_only=True, required=True)
    dragons_run = serializers.PrimaryKeyRelatedField(
        queryset=DRAGONSRun.objects.all(), write_only=True, required=True
    )

    class Meta(BaseDataProductSerializer.Meta):
        fields = (
            "id",
            "filepath",
            "filename",
            "dragons_run",
            "data_product_type",
            "data",
            "extra_data",
        )

    def validate(self, data):
        # Construct full path using MEDIA_ROOT and provided path
        full_path = settings.MEDIA_ROOT / data["filepath"] / data["filename"]
        if not default_storage.exists(full_path):
            raise serializers.ValidationError(
                "The specified file does not exist at the provided location."
            )
        return data

    def create(self, validated_data):
        fullpath = Path(validated_data.pop("filepath")) / validated_data.pop("filename")
        dragons_run = validated_data.pop("dragons_run")
        observation_record = dragons_run.observation_record

        # TODO: Determine the data_product_type for these special cases.
        data_product_type = validated_data.pop("data_product_type", "fits_file")

        target = observation_record.target
        product_id = str(fullpath)
        validated_data.update(
            {
                "product_id": product_id,
                "target": target,
                "observation_record": observation_record,
                "data_product_type": data_product_type,
            }
        )

        # Call the base method to handle the creation and manage groups.
        dp = super().create(validated_data)

        # Since the runs are stored in the local storage, don't need to copy.
        dp.data.name = f"{fullpath}"
        dp.save()

        return dp
