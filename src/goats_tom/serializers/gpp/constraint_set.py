"""
Serializer for GPP constraint set input data.
"""

__all__ = ["ConstraintSetSerializer"]

from typing import Any

from gpp_client.api.enums import (
    CloudExtinctionPreset,
    ImageQualityPreset,
    SkyBackground,
    WaterVapor,
)
from gpp_client.api.input_types import ConstraintSetInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer
from .elevation_range import ElevationRangeSerializer


class ConstraintSetSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP constraint set input data.
    """

    imageQualitySelect = serializers.ChoiceField(
        choices=[c.value for c in ImageQualityPreset],
        required=False,
        allow_blank=False,
    )
    cloudExtinctionSelect = serializers.ChoiceField(
        choices=[c.value for c in CloudExtinctionPreset],
        required=False,
        allow_blank=False,
    )
    skyBackgroundSelect = serializers.ChoiceField(
        choices=[c.value for c in SkyBackground],
        required=False,
        allow_blank=False,
    )
    waterVaporSelect = serializers.ChoiceField(
        choices=[c.value for c in WaterVapor],
        required=False,
        allow_blank=False,
    )

    pydantic_model = ConstraintSetInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the constraint set fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized target data.
        """
        internal = super().to_internal_value(data)

        self._elevation_range_serializer = ElevationRangeSerializer(data=data)
        self._elevation_range_serializer.is_valid(raise_exception=True)

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the constraint set input for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GPP or ``None`` if data is empty.
        """
        result: dict[str, Any] = {}
        data = self.validated_data

        # Format elevation range.
        elevation_range_data = self._elevation_range_serializer.format_gpp()
        if elevation_range_data is not None:
            result["elevationRange"] = elevation_range_data
        if (v := data.get("imageQualitySelect")) is not None:
            result["imageQuality"] = v
        if (v := data.get("cloudExtinctionSelect")) is not None:
            result["cloudExtinction"] = v
        if (v := data.get("skyBackgroundSelect")) is not None:
            result["skyBackground"] = v
        if (v := data.get("waterVaporSelect")) is not None:
            result["waterVapor"] = v

        return result if result else None
