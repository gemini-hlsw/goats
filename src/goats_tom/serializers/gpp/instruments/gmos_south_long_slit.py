"""
Serializer for GMOS-South long slit input data. This serializer is identical to the
GMOS-North long slit serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSSouthLongSlitSerializer"]

from typing import Any

from gpp_client.api.input_types import GmosSouthLongSlitInput
from rest_framework import serializers

from .._base_gpp import _BaseGPPSerializer
from .fields import CommaSeparatedFloatField


class GMOSSouthLongSlitSerializer(_BaseGPPSerializer):
    """Serializer for GMOS-South long slit input data."""

    centralWavelengthInput = serializers.FloatField(required=False, allow_null=True)
    spatialOffsetsInput = CommaSeparatedFloatField(required=False, allow_null=True)
    wavelengthDithersInput = CommaSeparatedFloatField(required=False, allow_null=True)

    pydantic_model = GmosSouthLongSlitInput

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format validated GMOS-South Long Slit data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GmosSouthLongSlitInput,
            or ``None`` if no relevant fields are provided.
        """
        data = self.validated_data
        result: dict[str, Any] = {}

        if (cw := data.get("centralWavelengthInput")) is not None:
            result["centralWavelength"] = {"nanometers": cw}

        if (wd := data.get("wavelengthDithersInput")) is not None:
            result["explicitWavelengthDithers"] = [{"nanometers": v} for v in wd]

        if (so := data.get("spatialOffsetsInput")) is not None:
            result["explicitOffsets"] = [{"arcseconds": v} for v in so]

        return result if result else None
