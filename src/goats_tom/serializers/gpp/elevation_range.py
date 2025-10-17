__all__ = ["ElevationRangeSerializer"]

from typing import Any

from rest_framework import serializers

from .utils import normalize


class ElevationRangeSerializer(serializers.Serializer):
    """Serializer to parse and validate elevation range from flat form data."""

    elevationRangeSelect = serializers.ChoiceField(choices=["Air Mass", "Hour Angle"])
    airMassMinimumInput = serializers.CharField(required=False, allow_blank=True)
    airMassMaximumInput = serializers.CharField(required=False, allow_blank=True)
    haMinimumInput = serializers.CharField(required=False, allow_blank=True)
    haMaximumInput = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and structure elevation range input into the correct nested model
        shape.

        Returns
        -------
        dict[str, Any]
            The structured elevation range data.

        Raises
        ------
        serializers.ValidationError
            If required fields are missing or invalid based on the selected mode.
        """

        mode = data["elevationRangeSelect"]

        # Handle Air Mass mode.
        if mode == "Air Mass":
            min_val = normalize(data.get("airMassMinimumInput"))
            max_val = normalize(data.get("airMassMaximumInput"))

            # At least one of min or max must be provided.
            if min_val is None and max_val is None:
                raise serializers.ValidationError(
                    "Air mass range must have at least one value."
                )

            # Build and return the structured data.
            try:
                return {
                    "airMass": {
                        "min": float(min_val) if min_val is not None else None,
                        "max": float(max_val) if max_val is not None else None,
                    }
                }
            except ValueError:
                raise serializers.ValidationError("Air mass values must be numeric.")

        # Handle Hour Angle mode.
        elif mode == "Hour Angle":
            min_val = normalize(data.get("haMinimumInput"))
            max_val = normalize(data.get("haMaximumInput"))

            # At least one of min or max must be provided.
            if min_val is None and max_val is None:
                raise serializers.ValidationError(
                    "Hour angle range must have at least one value."
                )

            # Build and return the structured data.
            try:
                return {
                    "hourAngle": {
                        "minHours": float(min_val) if min_val is not None else None,
                        "maxHours": float(max_val) if max_val is not None else None,
                    }
                }
            except ValueError:
                raise serializers.ValidationError("Hour angle values must be numeric.")

        # If mode is neither "Air Mass" nor "Hour Angle", raise an error.
        raise serializers.ValidationError("Invalid elevation range mode selected.")
