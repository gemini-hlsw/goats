"""Module to serializer data for `DRAGONSFile` model."""

__all__ = ["DRAGONSFileSerializer", "DRAGONSFileFilterSerializer"]

from urllib.parse import unquote

from rest_framework import serializers

from goats_tom.models import DRAGONSFile


class DRAGONSFileSerializer(serializers.ModelSerializer):
    """Serializer for `DRAGONSFile` model."""

    class Meta:
        model = DRAGONSFile
        fields = [
            "id",
            "dragons_run",
            "product_id",
            "url",
            "observation_id",
            "observation_type",
            "object_name",
            "observation_class",
        ]
        read_only_fields = [
            "id",
            "dragons_run",
            "product_id",
            "url",
            "observation_id",
            "observation_type",
            "object_name",
            "observation_class",
        ]


class DRAGONSFileFilterSerializer(serializers.Serializer):
    dragons_run = serializers.IntegerField(required=False)
    include = serializers.ListField(
        child=serializers.ChoiceField(choices=["astrodata_descriptors", "groups"]),
        required=False,
    )
    group_by = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="A list of groups to filter by.",
    )
    filter_expression = serializers.CharField(required=False, allow_blank=True)
    filter_strict = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Use a tolerance for filtering numeric values.",
    )

    def to_internal_value(self, data):
        new_data = data.copy()
        new_data["filter_expression"] = unquote(data.get("filter_expression", ""))
        return super().to_internal_value(new_data)
