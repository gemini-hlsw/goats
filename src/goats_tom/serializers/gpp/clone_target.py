"""
Clone Target Serializer for the GPP module.
"""

__all__ = ["CloneTargetSerializer"]

from typing import Any

from rest_framework import serializers

from ._base import _BaseSerializer


class CloneTargetSerializer(_BaseSerializer):
    """
    Serializer for cloning target data.
    """

    hiddenTargetIdInput = serializers.CharField(
        required=True, allow_null=False, allow_blank=False
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Perform cross-field validation and build the structured data for the clone
        target.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data dictionary.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.
        """
        # Assign target ID and target if provided.
        self._target_id = data.get("hiddenTargetIdInput")
        return data

    @property
    def target_id(self) -> str | None:
        return getattr(self, "_target_id", None)
