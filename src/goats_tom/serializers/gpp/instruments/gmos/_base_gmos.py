"""
Base serializer for GMOS instrument-specific fields.
"""

__all__ = ["_BaseGMOSSerializer"]

from typing import Any

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.instruments.gmos.exposure_mode import (
    ExposureModeSerializer,
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
        """
        internal = super().to_internal_value(data)

        self._exposure_mode_serializer = ExposureModeSerializer(data=data)
        self._exposure_mode_serializer.is_valid(raise_exception=True)

        return internal
