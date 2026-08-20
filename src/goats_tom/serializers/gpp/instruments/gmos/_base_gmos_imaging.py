"""
Base serializer for GMOS imaging instrument-specific fields.
"""

__all__ = ["_BaseGMOSImagingSerializer"]

import json
from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.instruments.gmos.imaging_variant import (
    ImagingVariantSerializer,
)


class _BaseGMOSImagingSerializer(_BaseGPPSerializer):
    """
    Base serializer for GMOS imaging input data.

    Only the offset variant is editable in the observation form; filters,
    binning, read mode and ROI are displayed read-only and are not submitted.
    This does not extend the long-slit GMOS base because that one requires an
    exposure mode, which imaging never sends.
    """

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
        if self.variant is None:
            return None

        variant_data = self.variant.format_gpp()

        return {"variant": variant_data} if variant_data else None

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
