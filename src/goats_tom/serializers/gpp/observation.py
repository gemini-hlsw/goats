"""
Serializer for GPP observation input data.
"""

__all__ = ["ObservationSerializer"]

from typing import Any

from gpp_client.generated.enums import ObservationPriority
from gpp_client.generated.input_types import ObservationPropertiesInput
from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer
from goats_tom.serializers.gpp.constraint_set import ConstraintSetSerializer
from goats_tom.serializers.gpp.finder_chart import FinderChartsSerializer
from goats_tom.serializers.gpp.observing_mode import ObservingModeSerializer
from goats_tom.serializers.gpp.pos_angle import PosAngleSerializer
from goats_tom.serializers.gpp.scheduling_constraints import (
    SchedulingConstraintsSerializer,
)
from goats_tom.serializers.gpp.science_band import ScienceBandSerializer


class ObservationSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP observation input data.
    """

    pydantic_model = ObservationPropertiesInput

    observerNotesTextarea = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    prioritySelect = serializers.ChoiceField(
        choices=[c.value for c in ObservationPriority],
        required=False,
        allow_blank=False,
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

        self._scheduling_constraints_serializer = SchedulingConstraintsSerializer(
            data=data
        )
        self._scheduling_constraints_serializer.is_valid(raise_exception=True)

        self._science_band_serializer = ScienceBandSerializer(data=data)
        self._science_band_serializer.is_valid(raise_exception=True)

        self._finder_charts_serializer = FinderChartsSerializer(data=data)
        self._finder_charts_serializer.is_valid(raise_exception=True)

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

        if (priority := self.validated_data.get("prioritySelect")) is not None:
            result["priority"] = priority

        observing_mode_data = self._observing_mode_serializer.format_gpp()
        if observing_mode_data is not None:
            result["observingMode"] = observing_mode_data

        constraint_set_data = self._constraint_set_serializer.format_gpp()
        if constraint_set_data is not None:
            result["constraintSet"] = constraint_set_data

        pos_angle_data = self._pos_angle_serializer.format_gpp()
        if pos_angle_data is not None:
            result["posAngleConstraint"] = pos_angle_data

        # GPP rejects the deprecated top-level `timingWindows` next to these.
        scheduling_constraints_data = (
            self._scheduling_constraints_serializer.format_gpp()
        )
        if scheduling_constraints_data is not None:
            result["schedulingConstraints"] = scheduling_constraints_data

        science_band_data = self._science_band_serializer.format_gpp()
        if science_band_data is not None:
            result["scienceBand"] = science_band_data

        return result if result else None
