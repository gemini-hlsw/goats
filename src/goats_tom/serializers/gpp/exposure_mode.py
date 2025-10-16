__all__ = ["GPPExposureModeSerializer"]

from typing import Any

from rest_framework import serializers

from .utils import normalize


class WavelengthSerializer(serializers.Serializer):
    """Serializer for wavelength values."""

    nanometers = serializers.FloatField()


class TimeSpanSerializer(serializers.Serializer):
    """Serializer for time span values."""

    seconds = serializers.FloatField()


class SignalToNoiseExposureSerializer(serializers.Serializer):
    """Serializer for signal-to-noise exposure mode."""

    value = serializers.FloatField()
    at = WavelengthSerializer()


class TimeAndCountExposureSerializer(serializers.Serializer):
    """Serializer for time and count exposure mode."""

    time = TimeSpanSerializer()
    count = serializers.IntegerField(min_value=1)
    at = WavelengthSerializer()


class GPPExposureModeSerializer(serializers.Serializer):
    """Serializer to parse and validate exposure mode from flat form data."""

    exposureModeSelect = serializers.ChoiceField(
        choices=["Signal / Noise", "Fixed Exposure"]
    )
    snInput = serializers.CharField(required=False, allow_blank=True)
    snWavelengthInput = serializers.CharField(required=False, allow_blank=True)
    exposureTimeInput = serializers.CharField(required=False, allow_blank=True)
    numExposuresInput = serializers.CharField(required=False, allow_blank=True)
    countWavelengthInput = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and structure exposure mode input into the correct nested model shape.

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

        # Handle Signal-to-Noise Mode
        if mode == "Signal / Noise":
            sn_value = normalize(data.get("snInput"))
            sn_wavelength = normalize(data.get("snWavelengthInput"))

            if sn_value is None or sn_wavelength is None:
                raise serializers.ValidationError("Missing signal-to-noise input(s).")

            # Build and return the structured data.
            try:
                return {
                    "signalToNoise": {
                        "value": float(sn_value),
                        "at": {"nanometers": float(sn_wavelength)},
                    }
                }
            except ValueError:
                raise serializers.ValidationError(
                    "Signal-to-noise values must be numeric."
                )

        # Handle Fixed Exposure Mode
        elif mode == "Fixed Exposure":
            exposure_time = normalize(data.get("exposureTimeInput"))
            num_exposures = normalize(data.get("numExposuresInput"))
            count_wavelength = normalize(data.get("countWavelengthInput"))

            if (
                exposure_time is None
                or num_exposures is None
                or count_wavelength is None
            ):
                raise serializers.ValidationError("Missing fixed exposure input(s).")

            # Build and return the structured data.
            try:
                return {
                    "timeAndCount": {
                        "time": {"seconds": float(exposure_time)},
                        "count": int(num_exposures),
                        "at": {"nanometers": float(count_wavelength)},
                    }
                }
            except ValueError:
                raise serializers.ValidationError(
                    "Fixed exposure values must be numeric."
                )

        # Raise error for unrecognized mode.
        raise serializers.ValidationError("Invalid exposure mode selected.")
