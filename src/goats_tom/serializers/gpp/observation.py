"""
Serializer for GPP observation input data.
"""

__all__ = ["ObservationSerializer"]

from typing import Any

from gpp_client.api.input_types import ObservationPropertiesInput
from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.constraint_set import ConstraintSetSerializer
from goats_tom.serializers.gpp.observing_mode import ObservingModeSerializer
from goats_tom.serializers.gpp.pos_angle import PosAngleSerializer
from goats_tom.serializers.gpp.scheduling_windows import SchedulingWindowsSerializer
from goats_tom.serializers.gpp.science_band import ScienceBandSerializer


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

        self._scheduling_windows_serializer = SchedulingWindowsSerializer(data=data)
        self._scheduling_windows_serializer.is_valid(raise_exception=True)

        self._science_band_serializer = ScienceBandSerializer(data=data)
        self._science_band_serializer.is_valid(raise_exception=True)

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

        scheduling_windows_data = self._scheduling_windows_serializer.format_gpp()
        if scheduling_windows_data is not None:
            result["timingWindows"] = scheduling_windows_data

        science_band_data = self._science_band_serializer.format_gpp()

        if science_band_data is not None:
            result["scienceBand"] = science_band_data

        return result if result else None
