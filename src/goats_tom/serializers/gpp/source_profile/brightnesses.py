__all__ = ["BrightnessesSerializer"]

import re
from typing import Any

from gpp_client.api.enums import Band, BrightnessIntegratedUnits
from gpp_client.api.input_types import BandBrightnessIntegratedInput
from rest_framework import serializers

from .._base_gpp import _BaseGPPSerializer


class _BrightnessSerializer(serializers.Serializer):
    """
    Serializer for individual brightness entries.

    Notes
    -----
    This serializer is tied to
    ``gpp_client.api.input_types.BandNormalizedIntegratedInput.`` and will eventually
    need to support all types of ``SourceProfileInput``.
    """

    band = serializers.ChoiceField(choices=[c.value for c in Band])
    value = serializers.FloatField()
    units = serializers.ChoiceField(
        choices=[c.value for c in BrightnessIntegratedUnits]
    )
    error = serializers.FloatField(required=False, allow_null=True)


class BrightnessesSerializer(_BaseGPPSerializer):
    """Serializer to parse and validate brightness entries from flat form data."""

    brightnesses = serializers.ListField(
        child=_BrightnessSerializer(),
        allow_empty=True,
        allow_null=True,
        required=False,
        default=None,
    )

    pydantic_model = BandBrightnessIntegratedInput

    # Regex pattern to capture brightness field names and indices.
    _brightness_pattern = re.compile(
        r"brightness(ValueInput|BandSelect|UnitsSelect|ErrorInput)(\d+)"
    )

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse flat brightness fields into structured brightnesses list.

        Parameters
        ----------
        data : dict[str, Any]
            The input data potentially containing brightness fields.

        Returns
        -------
        dict[str, Any]
            The structured brightnesses list or an error message.

        Raises
        ------
        serializers.ValidationError
            If any brightness value is invalid or required fields are missing.
        """
        brightnesses_data: dict[int, dict[str, Any]] = {}

        # Group brightness fields by their index.
        for key, value in data.items():
            match = self._brightness_pattern.match(key)
            if not match:
                continue

            field_type, index = match.groups()
            index = int(index)

            # Initialize dictionary for this index if not already present.
            brightnesses_data.setdefault(index, {})[field_type] = value

        # Normalize values.
        parsed: list[dict[str, Any]] = []
        for _, entry in sorted(brightnesses_data.items()):
            try:
                value = float(entry["ValueInput"])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(
                    "A Brightness value is not a valid number."
                )

            band = entry.get("BandSelect")
            units = entry.get("UnitsSelect")
            # Not supporting error parsing for now; optional field.

            # Ensure band and unit are provided.
            if not band or not units:
                raise serializers.ValidationError(
                    "A Brightness is missing a band or units."
                )

            # Put in parsed format expected by BrightnessSerializer.
            parsed.append(
                {
                    "band": band,
                    "value": value,
                    "units": units,
                }
            )

        return {"brightnesses": parsed or None}

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format validated brightness data into GPP input format.

        Returns
        -------
        dict[str, Any] | None
            The formatted brightness data, or ``None`` if not provided.
        """
        data = self.validated_data.get("brightnesses")
        if not data:
            return None

        return {"brightnesses": data}
