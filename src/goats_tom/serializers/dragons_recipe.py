"""Serializers for `DRAGONSRecipe`."""

__all__ = ["DRAGONSRecipeSerializer", "DRAGONSRecipeFilterSerializer"]

from rest_framework import serializers

from goats_tom.models import DRAGONSRecipe


class DRAGONSRecipeSerializer(serializers.ModelSerializer):
    """Serializer for `DRAGONSRecipe` models."""

    class Meta:
        model = DRAGONSRecipe
        fields = (
            "id",
            "observation_type",
            "name",
            "active_function_definition",
            "short_name",
            "version",
            "function_definition",
            "is_default",
            "instrument",
            "recipes_module_name",
            "object_name",
            "uparms",
            "observation_class",
            "dragons_run",
            "reduction_mode",
            "drpkg",
            "additional_files",
            "ucals",
            "suffix",
        )
        read_only_fields = (
            "id",
            "observation_type",
            "name",
            "short_name",
            "version",
            "active_function_definition",
            "is_default",
            "instrument",
            "recipes_module_name",
            "object_name",
            "observation_class",
            "dragons_run",
        )
        extra_kwargs = {"function_definition": {"write_only": True}}

    def update(self, instance: DRAGONSRecipe, validated_data: dict) -> DRAGONSRecipe:
        """Update specific fields of a DRAGONSRecipe instance with new data.

        Parameters
        ----------
        instance : `DRAGONSRecipe`
            The `DRAGONSRecipe` instance to update.
        validated_data : `dict`
            A dictionary containing the data to update, which may include
            'uparms' and 'function_definition' fields.

        Returns
        -------
        `DRAGONSRecipe`
            The updated `DRAGONSRecipe` instance.

        """
        fields_to_update = [
            "uparms",
            "function_definition",
            "reduction_mode",
            "drpkg",
            "additional_files",
            "ucals",
            "suffix",
        ]
        # Flag to track if any data has been changed.
        changed = False
        for field in fields_to_update:
            if field in validated_data:
                new_value = validated_data[field]
                # Check if new_value is None or empty after potential stripping.
                if new_value is not None and new_value.strip() == "":
                    new_value = None
                # Only assign new value if it has changed.
                if getattr(instance, field) != new_value:
                    setattr(instance, field, new_value)
                    changed = True

        # Only save if something has changed.
        if changed:
            instance.save()

        return instance


class DRAGONSRecipeFilterSerializer(serializers.Serializer):
    """Serializer for filtering `DRAGONS` recipes."""

    dragons_run = serializers.IntegerField(
        required=False,
        help_text="Primary key for the DRAGONS run to filter by.",
    )
    include = serializers.ListField(
        child=serializers.ChoiceField(choices=["help", "groups"]),
        required=False,
    )
    # Values to allow grouping for display, change this to add more grouping.
    group_by = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["observation_type", "observation_class", "object_name"]
        ),
        required=False,
        allow_empty=True,
        help_text="A list of groups to filter by.",
    )
    version = serializers.CharField(
        required=False,
        help_text="DRAGONS version to filter recipes by.",
    )
