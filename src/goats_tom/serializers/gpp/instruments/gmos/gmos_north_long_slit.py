"""
Serializer for GMOS-North long slit input data. This serializer is identical to the
GMOS-South long slit serializer but is kept separate for clarity and potential future
differences.
"""

__all__ = ["GMOSNorthLongSlitSerializer"]

from typing import Any

from gpp_client.generated.enums import (
    GmosNorthBuiltinFpu,
    GmosNorthFilter,
    GmosNorthGrating,
)
from gpp_client.generated.input_types import GmosNorthLongSlitInput
from rest_framework import serializers

from goats_tom.serializers.gpp.instruments.fields import CommaSeparatedFloatField
from goats_tom.serializers.gpp.instruments.gmos._base_gmos import _BaseGMOSSerializer


class GMOSNorthLongSlitSerializer(_BaseGMOSSerializer):
    """Serializer for GMOS-North long slit input data."""

    centralWavelengthInput = serializers.FloatField(required=False, allow_null=True)
    # Only sent when creating from an approved configuration; updating an
    # existing observation leaves the optics alone.
    hiddenGratingInput = serializers.ChoiceField(
        choices=[g.value for g in GmosNorthGrating],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    fpuSelect = serializers.ChoiceField(
        choices=[f.value for f in GmosNorthBuiltinFpu],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    filterSelect = serializers.ChoiceField(
        choices=[f.value for f in GmosNorthFilter],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    spatialOffsetsInput = CommaSeparatedFloatField(required=False, allow_null=True)
    wavelengthDithersInput = CommaSeparatedFloatField(required=False, allow_null=True)

    pydantic_model = GmosNorthLongSlitInput

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format validated GMOS-North Long Slit data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GmosNorthLongSlitInput,
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
