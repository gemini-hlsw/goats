"""
Clone Target Serializer for the GPP module.
"""

__all__ = ["CloneTargetSerializer"]

from typing import Any

from rest_framework import serializers

from ._base import _BaseSerializer


class CloneTargetSerializer(_BaseSerializer):
    """Serializer for cloning target data.

    This serializer processes hidden input fields related to target cloning, such as
    target ID, radial velocity, parallax, and proper motion.
    """

    hiddenTargetIdInput = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    radialVelocityInput = serializers.FloatField(required=False, allow_null=True)
    parallaxInput = serializers.FloatField(required=False, allow_null=True)
    uRaInput = serializers.FloatField(required=False, allow_null=True)
    uDecInput = serializers.FloatField(required=False, allow_null=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Perform cross-field validation and build the structured data for the clone
        target.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data dictionary.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.

        Notes
        -----
        - RA and Dec are set to dummy values as they are not modified via the ToO form.
        - The epoch is set to a standard value of "J2000".
        """
        # Assign target ID if provided.
        self._target_id = data.get("hiddenTargetIdInput")

        return {
            "sidereal": {
                "radialVelocity": {
                    "kilometersPerSecond": data.get("radialVelocityInput")
                },
                "parallax": {"milliarcseconds": data.get("parallaxInput")},
                "properMotion": {
                    "ra": {"milliarcsecondsPerYear": data.get("uRaInput")},
                    "dec": {"milliarcsecondsPerYear": data.get("uDecInput")},
                },
                # RA and Dec are not modified via TOO form, set to dummy values.
                "ra": {"degrees": None},
                "dec": {"degrees": None},
                # Use standard epoch.
                "epoch": "J2000",
            },
            # Placeholder for other serializer field.
            "sourceProfile": None,
        }

    @property
    def target_id(self) -> str | None:
        return getattr(self, "_target_id", None)
