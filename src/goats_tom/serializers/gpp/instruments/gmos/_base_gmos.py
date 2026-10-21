"""
Base serializer for GMOS instrument-specific fields.
"""

__all__ = ["_BaseGMOSSerializer"]

import json
from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.instruments.gmos.exposure_mode import (
    ExposureModeSerializer,
)
from goats_tom.serializers.gpp.instruments.gmos.slit_telescope_configs import (
    SlitTelescopeConfigsSerializer,
)


class _BaseGMOSSerializer(_BaseGPPSerializer):
    """
    Base serializer for GMOS instrument-specific fields.
    """

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate GMOS-specific fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized GMOS instrument data.

        Raises
        ------
        serializers.ValidationError
            If the spatial offsets are not valid JSON.
        """
        internal = super().to_internal_value(data)

        self._exposure_mode_serializer = ExposureModeSerializer(data=data)
        self._exposure_mode_serializer.is_valid(raise_exception=True)

        self._telescope_configs_serializer = None
        raw_configs = data.get("spatialOffsets")
        if raw_configs in (None, ""):
            return internal

        if isinstance(raw_configs, str):
            try:
                raw_configs = json.loads(raw_configs)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    {"spatialOffsets": "Invalid JSON for the spatial offsets."}
                )

        self._telescope_configs_serializer = SlitTelescopeConfigsSerializer(
            data=raw_configs
        )
        self._telescope_configs_serializer.is_valid(raise_exception=True)

        return internal
