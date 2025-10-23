"""
Serializer for GPP target input data.
"""

__all__ = ["TargetSerializer"]

from typing import Any

from gpp_client.api.input_types import TargetPropertiesInput

from ._base_gpp import _BaseGPPSerializer
from .sidereal import SiderealSerializer
from .source_profile import SourceProfileSerializer


class TargetSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP target input data.
    """

    pydantic_model = TargetPropertiesInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the target-specific fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized target data.
        """
        internal = super().to_internal_value(data)

        self._sidereal_serializer = SiderealSerializer(data=data)
        self._sidereal_serializer.is_valid(raise_exception=True)

        self._source_profile_serializer = SourceProfileSerializer(data=data)
        self._source_profile_serializer.is_valid(raise_exception=True)

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the target input for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GPP or ``None`` if data is invalid.
        """
        result: dict[str, Any] = {}

        sidereal_data = self._sidereal_serializer.format_gpp()
        if sidereal_data is not None:
            result["sidereal"] = sidereal_data

        source_profile_data = self._source_profile_serializer.format_gpp()
        if source_profile_data is not None:
            result["sourceProfile"] = source_profile_data

        return result if result else None
