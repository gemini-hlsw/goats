"""
Black body SED serializer.
"""

__all__ = ["BlackBodySerializer"]

from typing import Any

from gpp_client.api.input_types import UnnormalizedSedInput
from rest_framework import serializers

from ..._base_gpp import _BaseGPPSerializer


class BlackBodySerializer(_BaseGPPSerializer):
    sedBlackBodyTempK = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )

    pydantic_model = UnnormalizedSedInput

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the SED data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GPP or ``None`` if no data is present.
        """
        if (temp := self.validated_data.get("sedBlackBodyTempK")) is not None:
            return {"blackBodyTempK": temp}

        return None
