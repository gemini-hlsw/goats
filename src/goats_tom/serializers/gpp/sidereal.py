"""
Serializer for sidereal target properties.
"""

__all__ = ["SiderealSerializer"]

from typing import Any

from rest_framework import serializers
from tom_targets.models import BaseTarget as Target

from ._base import _BaseSerializer


class SiderealSerializer(_BaseSerializer):
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

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the input data for the sidereal properties.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data dictionary.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.
        """
        # Assign target instance.
        self._target = data.get("hiddenGoatsTargetIdInput")

        return {
            "radialVelocity": {"kilometersPerSecond": data.get("radialVelocityInput")},
            "parallax": {"milliarcseconds": data.get("parallaxInput")},
            "properMotion": {
                "ra": {"milliarcsecondsPerYear": data.get("uRaInput")},
                "dec": {"milliarcsecondsPerYear": data.get("uDecInput")},
            },
            # Update with target's RA and Dec.
            "ra": {"degrees": self._target.ra},
            "dec": {"degrees": self._target.dec},
            # Use standard epoch.
            "epoch": "J2000",
        }

    @property
    def target(self) -> Target | None:
        return getattr(self, "_target", None)
