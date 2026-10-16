"""
Serializer for GPP scheduling constraints input data.
"""

__all__ = ["SchedulingConstraintsSerializer"]

from typing import Any

from gpp_client.generated.enums import SchedulingMode, TooActivation
from gpp_client.generated.input_types import SchedulingConstraintsInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer
from .scheduling_windows import SchedulingWindowsSerializer

# GPP rejects any other scheduling mode while the activation is one of these.
UNINTERRUPTIBLE_ACTIVATIONS = {
    TooActivation.RAPID.value,
    TooActivation.INTERRUPTING.value,
}


class SchedulingConstraintsSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP scheduling constraints input data.
    """

    tooActivationSelect = serializers.ChoiceField(
        choices=[c.value for c in TooActivation],
        required=False,
        allow_blank=False,
    )
    schedulingModeSelect = serializers.ChoiceField(
        choices=[c.value for c in SchedulingMode],
        required=False,
        allow_blank=False,
    )

    pydantic_model = SchedulingConstraintsInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the scheduling constraint fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized scheduling constraints data.
        """
        internal = super().to_internal_value(data)

        self._scheduling_windows_serializer = SchedulingWindowsSerializer(data=data)
        self._scheduling_windows_serializer.is_valid(raise_exception=True)

        return internal

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Reject a scheduling mode the ToO activation does not allow.

        Parameters
        ----------
        attrs : dict[str, Any]
            The deserialized data.

        Returns
        -------
        dict[str, Any]
            The validated data.
        """
        mode = attrs.get("schedulingModeSelect")
        if (
            attrs.get("tooActivationSelect") in UNINTERRUPTIBLE_ACTIVATIONS
            and mode is not None
            and mode != SchedulingMode.UNINTERRUPTIBLE.value
        ):
            raise serializers.ValidationError(
                {
                    "schedulingModeSelect": "Must be UNINTERRUPTIBLE while the ToO "
                    "activation is RAPID or INTERRUPTING."
                }
            )
        return attrs

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the scheduling constraints input for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GPP.
        """
        data = self.validated_data
        result: dict[str, Any] = {
            "timingWindows": self._scheduling_windows_serializer.format_gpp()
        }

        if (v := data.get("tooActivationSelect")) is not None:
            result["tooActivation"] = v
        if (v := data.get("schedulingModeSelect")) is not None:
            result["schedulingMode"] = v

        return result
