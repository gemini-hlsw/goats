"""
Serializer for GPP position angle constraint data.
"""

__all__ = ["PosAngleSerializer"]

from typing import Any

from gpp_client.api.enums import PosAngleConstraintMode
from gpp_client.api.input_types import PosAngleConstraintInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class PosAngleSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP position angle constraint data.
    """

    posAngleConstraintModeSelect = serializers.ChoiceField(
        choices=[c.value for c in PosAngleConstraintMode],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    posAngleConstraintAngleInput = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0, max_value=360.0
    )

    pydantic_model = PosAngleConstraintInput

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Perform cross-field validation only.

        Parameters
        ----------
        data : dict[str, Any]
            The validated form input data.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.
        """
        mode = data.get("posAngleConstraintModeSelect")
        angle = data.get("posAngleConstraintAngleInput")
        required_angle_modes = {
            PosAngleConstraintMode.FIXED.value,
            PosAngleConstraintMode.ALLOW_FLIP.value,
            PosAngleConstraintMode.PARALLACTIC_OVERRIDE.value,
        }
        # Validate mode-angle consistency.
        if mode in required_angle_modes and angle is None:
            raise serializers.ValidationError(
                {
                    "posAngleConstraintAngleInput": "Angle is required for the "
                    "selected mode."
                }
            )

        return data

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the validated position angle constraint data for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted position angle constraint data for GPP, or ``None``.
        """
        data = self.validated_data

        result: dict[str, Any] = {}
        result["mode"] = data["posAngleConstraintModeSelect"]
        if (angle := data.get("posAngleConstraintAngleInput")) is not None:
            result["angle"] = {"degrees": angle}

        return result if result else None
