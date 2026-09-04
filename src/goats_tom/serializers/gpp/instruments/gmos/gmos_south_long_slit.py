"""
Serializer for GMOS-South long slit input data. This serializer is identical to the
GMOS-North long slit serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSSouthLongSlitSerializer"]

from typing import Any

from gpp_client.generated.enums import (
    GmosSouthBuiltinFpu,
    GmosSouthFilter,
    GmosSouthGrating,
)
from gpp_client.generated.input_types import GmosSouthLongSlitInput
from rest_framework import serializers

from goats_tom.serializers.gpp.instruments.fields import CommaSeparatedFloatField
from goats_tom.serializers.gpp.instruments.gmos._base_gmos import _BaseGMOSSerializer


class GMOSSouthLongSlitSerializer(_BaseGMOSSerializer):
    """Serializer for GMOS-South long slit input data."""

    centralWavelengthInput = serializers.FloatField(required=False, allow_null=True)
    # Only sent when creating from an approved configuration; updating an
    # existing observation leaves the optics alone.
    hiddenGratingInput = serializers.ChoiceField(
        choices=[g.value for g in GmosSouthGrating],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    fpuSelect = serializers.ChoiceField(
        choices=[f.value for f in GmosSouthBuiltinFpu],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    filterSelect = serializers.ChoiceField(
        choices=[f.value for f in GmosSouthFilter],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
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

        if grating := data.get("hiddenGratingInput"):
            result["grating"] = grating

        if fpu := data.get("fpuSelect"):
            result["fpu"] = fpu

        if filter_ := data.get("filterSelect"):
            result["filter"] = filter_

        if (cw := data.get("centralWavelengthInput")) is not None:
            result["centralWavelength"] = {"nanometers": cw}

        if (wd := data.get("wavelengthDithersInput")) is not None:
            result["explicitWavelengthDithers"] = [{"nanometers": v} for v in wd]

        if (so := data.get("spatialOffsetsInput")) is not None:
            result["explicitOffsets"] = [{"arcseconds": v} for v in so]

        if self._exposure_mode_serializer is not None:
            exposure_mode_data = self._exposure_mode_serializer.format_gpp()
            if exposure_mode_data is not None:
                result["exposureTimeMode"] = exposure_mode_data

        return result if result else None
