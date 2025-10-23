"""
Serializer for GPP observation input data.
"""

__all__ = ["ObservationSerializer"]

from typing import Any

from gpp_client.api.input_types import ObservationPropertiesInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer
from .constraint_set import ConstraintSetSerializer
from .exposure_mode import ExposureModeSerializer
from .observing_mode import ObservingModeSerializer
from .pos_angle import PosAngleSerializer


class ObservationSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP observation input data.
    """

    pydantic_model = ObservationPropertiesInput

    observerNotesTextarea = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the observation-specific fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized observation data.
        """
        internal = super().to_internal_value(data)

        self._observing_mode_serializer = ObservingModeSerializer(data=data)
        self._observing_mode_serializer.is_valid(raise_exception=True)

        self._constraint_set_serializer = ConstraintSetSerializer(data=data)
        self._constraint_set_serializer.is_valid(raise_exception=True)

        self._pos_angle_serializer = PosAngleSerializer(data=data)
        self._pos_angle_serializer.is_valid(raise_exception=True)

        self._exposure_mode_serializer = ExposureModeSerializer(data=data)
        self._exposure_mode_serializer.is_valid(raise_exception=True)

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the observation input for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted data dictionary for GPP or ``None`` if data is not provided.
        """
        result: dict[str, Any] = {}

        if (
            observer_notes := self.validated_data.get("observerNotesTextarea")
        ) is not None:
            result["observerNotes"] = observer_notes

        observing_mode_data = self._observing_mode_serializer.format_gpp()
        if observing_mode_data is not None:
            result["observingMode"] = observing_mode_data

        constraint_set_data = self._constraint_set_serializer.format_gpp()
        if constraint_set_data is not None:
            result["constraintSet"] = constraint_set_data

        pos_angle_data = self._pos_angle_serializer.format_gpp()
        if pos_angle_data is not None:
            result["posAngleConstraint"] = pos_angle_data

        exposure_mode_data = self._exposure_mode_serializer.format_gpp()
        if exposure_mode_data is not None:
            result["scienceRequirements"] = {}
            result["scienceRequirements"]["exposureTimeMode"] = exposure_mode_data

        return result if result else None
