__all__ = ["GPPBrightnessesSerializer"]

import re
from typing import Any

from gpp_client.api.enums import Band, BrightnessIntegratedUnits
from rest_framework import serializers


class BrightnessSerializer(serializers.Serializer):
    """
    Serializer for individual brightness entries.

    Notes
    -----
    This serializer is tied to
    ``gpp_client.api.input_types.BandNormalizedIntegratedInput.`` and will eventually
    need to support all types of ``SourceProfileInput``.
    """

    band = serializers.ChoiceField(choices=[b.value for b in Band])
    value = serializers.FloatField()
    unit = serializers.ChoiceField(choices=[u.value for u in BrightnessIntegratedUnits])
    error = serializers.FloatField(required=False, allow_null=True)


class GPPBrightnessesSerializer(serializers.Serializer):
    """Serializer to parse and validate brightness entries from flat form data."""

    brightnesses = serializers.ListField(
        child=BrightnessSerializer(),
        allow_empty=True,
        allow_null=True,
        required=False,
        default=None,
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
        brightness_pattern = re.compile(
            r"brightness(ValueInput|BandSelect|UnitsSelect)(\d+)"
        )
        brightnesses_data: dict[int, dict[str, Any]] = {}

        # Group brightness fields by their index.
        for key, value in data.items():
            match = brightness_pattern.match(key)
            if not match:
                continue

            field_type, index = match.groups()
            index = int(index)

            # Handle list values from form submissions.
            raw_value = value[0] if isinstance(value, list) else value
            raw_value = raw_value.strip() if raw_value else None

            # Initialize dictionary for this index if not already present.
            brightnesses_data.setdefault(index, {})[field_type] = raw_value

        # Normalize values.
        parsed = []
        for index, entry in sorted(brightnesses_data.items()):
            try:
                value = float(entry["ValueInput"])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(
                    "A Brightness value is not a valid number."
                )

            band = entry.get("BandSelect")
            unit = entry.get("UnitsSelect")

            # Ensure band and unit are provided.
            if not band or not unit:
                raise serializers.ValidationError(
                    "A Brightness is missing a band or unit."
                )

            parsed.append(
                {
                    "band": band,
                    "value": value,
                    "unit": unit,
                }
            )

        # Return structured brightnesses or None if empty.
        if not parsed:
            return super().to_internal_value({"brightnesses": None})
        return super().to_internal_value({"brightnesses": parsed})
