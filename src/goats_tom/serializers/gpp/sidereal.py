"""
Serializer for sidereal target properties.
"""

__all__ = ["SiderealSerializer"]

from typing import Any

from gpp_client.api.input_types import SiderealInput
from rest_framework import serializers
from tom_targets.models import BaseTarget as Target

from ._base_gpp import _BaseGPPSerializer


class SiderealSerializer(_BaseGPPSerializer):
    """
    Serializer for sidereal target properties.
    """

    hiddenGoatsTargetIdInput = serializers.PrimaryKeyRelatedField(
        required=True, allow_null=False, queryset=Target.objects.all()
    )
    radialVelocityInput = serializers.FloatField(required=False, allow_null=True)
    parallaxInput = serializers.FloatField(required=False, allow_null=True)
    uRaInput = serializers.FloatField(required=False, allow_null=True)
    uDecInput = serializers.FloatField(required=False, allow_null=True)

    pydantic_model = SiderealInput

    def format_gpp(self) -> dict[str, Any]:
        """
        Format the sidereal target data for GPP.

        Returns
        -------
        dict[str, Any]
            The formatted data dictionary for GPP.
        """
        data = self.validated_data
        result: dict[str, Any] = {
            "ra": {"degrees": self.target.ra},
            "dec": {"degrees": self.target.dec},
            "epoch": "J2000.000",
        }

        if (rv := data.get("radialVelocityInput")) is not None:
            result["radialVelocity"] = {"kilometersPerSecond": rv}

        if (parallax := data.get("parallaxInput")) is not None:
            result["parallax"] = {"milliarcseconds": parallax}

        u_ra = data.get("uRaInput")
        u_dec = data.get("uDecInput")

        if u_ra is not None or u_dec is not None:
            result["properMotion"] = {}
            if u_ra is not None:
                result["properMotion"]["ra"] = {"milliarcsecondsPerYear": u_ra}
            if u_dec is not None:
                result["properMotion"]["dec"] = {"milliarcsecondsPerYear": u_dec}

        return result

    @property
    def target(self) -> Target:
        """
        Get the Target instance for the sidereal properties.

        Returns
        -------
        Target
            The Target instance.
        """
        return self.validated_data["hiddenGoatsTargetIdInput"]
