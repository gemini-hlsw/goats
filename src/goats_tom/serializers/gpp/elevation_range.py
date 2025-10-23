"""
Serializer for elevation range input data.
"""

__all__ = ["ElevationRangeSerializer"]

from typing import Any

from gpp_client.api.input_types import ElevationRangeInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class ElevationRangeSerializer(_BaseGPPSerializer):
    """Serializer to parse and validate elevation range from flat form data."""

    elevationRangeSelect = serializers.ChoiceField(
        choices=["Air Mass", "Hour Angle"],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    airMassMinimumInput = serializers.FloatField(required=False, allow_null=True)
    airMassMaximumInput = serializers.FloatField(required=False, allow_null=True)
    haMinimumInput = serializers.FloatField(required=False, allow_null=True)
    haMaximumInput = serializers.FloatField(required=False, allow_null=True)

    pydantic_model = ElevationRangeInput

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate elevation range.

        Parameters
        ----------
        data : dict[str, Any]
            The flat validated form data.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.

        Raises
        ------
        serializers.ValidationError
            If required fields are missing based on the selected mode.
        """
        mode = data["elevationRangeSelect"]

        if mode == "Air Mass":
            if (
                data.get("airMassMinimumInput") is None
                and data.get("airMassMaximumInput") is None
            ):
                raise serializers.ValidationError(
                    "At least one air mass boundary (min or max) must be provided."
                )

        elif mode == "Hour Angle":
            if (
                data.get("haMinimumInput") is None
                and data.get("haMaximumInput") is None
            ):
                raise serializers.ValidationError(
                    "At least one hour angle boundary (min or max) must be provided."
                )

        else:
            raise serializers.ValidationError("Invalid elevation range mode selected.")

        return data

    def format_gpp(self) -> dict[str, Any]:
        """
        Format validated elevation range data into GPP input format.

        Returns
        -------
        dict[str, Any]
            The formatted data dictionary for GPP input.
        """
        data = self.validated_data
        mode = data["elevationRangeSelect"]

        if mode == "Air Mass":
            air_mass: dict[str, float] = {}
            if data.get("airMassMinimumInput") is not None:
                air_mass["min"] = data["airMassMinimumInput"]
            if data.get("airMassMaximumInput") is not None:
                air_mass["max"] = data["airMassMaximumInput"]
            return {"airMass": air_mass}

        if mode == "Hour Angle":
            hour_angle: dict[str, float] = {}
            if data.get("haMinimumInput") is not None:
                hour_angle["minHours"] = data["haMinimumInput"]
            if data.get("haMaximumInput") is not None:
                hour_angle["maxHours"] = data["haMaximumInput"]
            return {"hourAngle": hour_angle}

        # Defensive fallback, should never get here.
        raise serializers.ValidationError("Invalid elevation range mode selected.")
