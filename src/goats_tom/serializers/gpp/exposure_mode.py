"""
Serializer to parse and validate exposure mode from flat form data.
"""

__all__ = ["ExposureModeSerializer"]

from typing import Any

from gpp_client.api.input_types import ExposureTimeModeInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class ExposureModeSerializer(_BaseGPPSerializer):
    """Serializer to parse and validate exposure mode from flat form data."""

    exposureModeSelect = serializers.ChoiceField(
        choices=["Signal / Noise", "Time & Count"],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    snInput = serializers.FloatField(required=False, allow_null=True)
    snWavelengthInput = serializers.FloatField(required=False, allow_null=True)
    exposureTimeInput = serializers.FloatField(required=False, allow_null=True)
    numExposuresInput = serializers.IntegerField(required=False, allow_null=True)
    countWavelengthInput = serializers.FloatField(required=False, allow_null=True)

    pydantic_model = ExposureTimeModeInput

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the input.

        Parameters
        ----------
        data : dict[str, Any]
            The input data containing exposure mode fields.

        Returns
        -------
        dict[str, Any]
            The structured exposure mode data.

        Raises
        ------
        serializers.ValidationError
            If required fields are missing or invalid based on the selected mode.
        """

        mode = data.get("exposureModeSelect")

        if mode == "Signal / Noise":
            if data.get("snInput") is None or data.get("snWavelengthInput") is None:
                raise serializers.ValidationError(
                    "Both S/N value and wavelength are required for "
                    "Signal / Noise mode."
                )

        elif mode == "Time & Count":
            if (
                data.get("exposureTimeInput") is None
                or data.get("numExposuresInput") is None
                or data.get("countWavelengthInput") is None
            ):
                raise serializers.ValidationError(
                    "Exposure time, number of exposures, and wavelength are required "
                    "for Time & Count mode."
                )

        else:
            raise serializers.ValidationError("Invalid exposure mode selected.")

        return data

    def format_gpp(self) -> dict[str, Any]:
        """
        Format validated exposure mode data into GPP input format.

        Returns
        -------
        dict[str, Any]
            The formatted data for GPP input.
        """
        data = self.validated_data
        mode = data["exposureModeSelect"]

        if mode == "Signal / Noise":
            return {
                "signalToNoise": {
                    "value": data["snInput"],
                    "at": {"nanometers": data["snWavelengthInput"]},
                }
            }

        if mode == "Time & Count":
            return {
                "timeAndCount": {
                    "time": {"seconds": data["exposureTimeInput"]},
                    "count": data["numExposuresInput"],
                    "at": {"nanometers": data["countWavelengthInput"]},
                }
            }

        # Defensive fallback, though DRF validation ensures this never runs.
        raise serializers.ValidationError("Invalid exposure mode selected.")
