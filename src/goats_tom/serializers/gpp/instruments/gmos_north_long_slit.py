"""
Serializer for GMOS-North long slit input data. This serializer is identical to the
GMOS-South long slit serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSNorthLongSlitSerializer"]

from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp.utils import normalize, parse_comma_separated_floats


class GMOSNorthLongSlitSerializer(serializers.Serializer):
    """Serializer for GMOS-North long slit input data."""

    centralWavelengthInput = serializers.CharField(required=False, allow_blank=True)
    spatialOffsetsInput = serializers.CharField(required=False, allow_blank=True)
    wavelengthDithersInput = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and structure GMOS-North Long Slit fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw form input data.

        Returns
        -------
        dict[str, Any]
            The structured GraphQL-ready data for GmosNorthLongSlitInput.

        Raises
        ------
        serializers.ValidationError
            If any values are invalid or incorrectly formatted.
        """
        result: dict[str, Any] = {}

        # Handle central wavelength.
        central = normalize(data.get("centralWavelengthInput"))
        if central is not None:
            try:
                result["centralWavelength"] = {"nanometers": float(central)}
            except ValueError:
                raise serializers.ValidationError(
                    "centralWavelengthInput must be a numeric value in nanometers."
                )

        # Handle wavelength dithers.
        dithers = normalize(data.get("wavelengthDithersInput"))
        if dithers:
            result["explicitWavelengthDithers"] = parse_comma_separated_floats(
                dithers, "wavelengthDithersInput", "nanometers"
            )

        # Handle spatial offsets.
        offsets = normalize(data.get("spatialOffsetsInput"))
        if offsets:
            result["explicitOffsets"] = parse_comma_separated_floats(
                offsets, "spatialOffsetsInput", "arcseconds"
            )

        # Return the structured data from the serializer with the instrument key.
        return {"gmos_north_long_slit": result}
