"""Module that serializes metadata."""

__all__ = ["DataProductMetadataSerializer"]

from rest_framework import serializers

from goats_tom.models import DataProductMetadata


class DataProductMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataProductMetadata
        fields = ("processed",)
