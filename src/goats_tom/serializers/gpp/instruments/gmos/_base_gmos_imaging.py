"""
Base serializer for GMOS imaging instrument-specific fields.
"""

__all__ = ["_BaseGMOSImagingSerializer"]

import json
from enum import Enum
from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.instruments.gmos.exposure_mode import (
    ExposureModeSerializer,
)
from goats_tom.serializers.gpp.instruments.gmos.imaging_variant import (
    ImagingVariantSerializer,
)


class _BaseGMOSImagingSerializer(_BaseGPPSerializer):
    """
    Base serializer for GMOS imaging input data.

    Updating an observation only submits the offset variant; filters, binning,
    read mode and ROI are displayed read-only. Creating one from an approved
    configuration also submits that configuration's filters, together with a
    single exposure time mode applied to all of them. This does not extend the
    long-slit GMOS base because that one always requires an exposure mode.
    """

    filter_enum: type[Enum] | None = None
    """The site specific filter enum, defined by the subclasses."""

    hiddenImagingFiltersInput = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate_hiddenImagingFiltersInput(self, value: str) -> list[str]:
        """
        Validate the comma separated filters against the instrument enum.

        Parameters
        ----------
        value : str
            The comma separated filters.

        Returns
        -------
        list[str]
            The parsed filters.

        Raises
        ------
        serializers.ValidationError
            If any filter is unknown to the instrument.
        """
        filters = [f.strip() for f in value.split(",") if f.strip()]
        allowed = {f.value for f in self.filter_enum} if self.filter_enum else set()
        unknown = [f for f in filters if f not in allowed]
        if unknown:
            raise serializers.ValidationError(
                f"Unknown filters for this instrument: {', '.join(unknown)}."
            )
        return filters

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the offset variant.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized imaging data.

        Raises
        ------
        serializers.ValidationError
            If the offset variant is not valid JSON.
        """
        internal = super().to_internal_value(data)
        self._variant_serializer = None
        self._exposure_mode_serializer = None

        # Only creating from an approved configuration submits an exposure mode.
        if data.get("exposureModeSelect"):
            exposure_mode_serializer = ExposureModeSerializer(data=data)
            exposure_mode_serializer.is_valid(raise_exception=True)
            self._exposure_mode_serializer = exposure_mode_serializer

        raw_variant = data.get("imagingOffsetVariant")
        if raw_variant in (None, ""):
            return internal

        if isinstance(raw_variant, str):
            try:
                raw_variant = json.loads(raw_variant)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    {"imagingOffsetVariant": "Invalid JSON for the offset variant."}
                )

        self._variant_serializer = ImagingVariantSerializer(data=raw_variant)
        self._variant_serializer.is_valid(raise_exception=True)

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format validated GMOS imaging data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted imaging input, or ``None`` if nothing was submitted.
        """
        result: dict[str, Any] = {}

        if self.variant is not None:
            variant_data = self.variant.format_gpp()
            if variant_data:
                result["variant"] = variant_data

        filters = self.validated_data.get("hiddenImagingFiltersInput") or []
        if filters:
            exposure_mode = (
                self._exposure_mode_serializer.format_gpp()
                if self._exposure_mode_serializer is not None
                else None
            )
            result["filters"] = [
                {
                    "filter": f,
                    **({"exposureTimeMode": exposure_mode} if exposure_mode else {}),
                }
                for f in filters
            ]

        return result if result else None

    @property
    def variant(self) -> ImagingVariantSerializer | None:
        """
        Get the validated offset variant serializer instance.

        Returns
        -------
        ImagingVariantSerializer | None
            The variant serializer, or ``None`` if none was submitted.
        """
        return getattr(self, "_variant_serializer", None)
