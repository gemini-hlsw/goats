"""
Clone Observation Serializer for the GPP module.
"""

__all__ = ["CloneObservationSerializer"]

from typing import Any

from gpp_client.api.enums import (
    CloudExtinctionPreset,
    ImageQualityPreset,
    PosAngleConstraintMode,
    SkyBackground,
    WaterVapor,
)
from rest_framework import serializers

from ._base import _BaseSerializer


class CloneObservationSerializer(_BaseSerializer):
    """
    Serializer for cloning observation data.

    This serializer processes hidden input fields related to observation cloning, such
    as observation ID, observing mode, and various constraints.
    """

    hiddenObservationIdInput = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    hiddenObservingModeInput = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    observerNotesTextarea = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    imageQualitySelect = serializers.ChoiceField(
        choices=[c.value for c in ImageQualityPreset], required=False, allow_blank=False
    )
    cloudExtinctionSelect = serializers.ChoiceField(
        choices=[c.value for c in CloudExtinctionPreset],
        required=False,
        allow_blank=False,
    )
    skyBackgroundSelect = serializers.ChoiceField(
        choices=[c.value for c in SkyBackground], required=False, allow_blank=False
    )
    waterVaporSelect = serializers.ChoiceField(
        choices=[c.value for c in WaterVapor], required=False, allow_blank=False
    )
    posAngleConstraintModeSelect = serializers.ChoiceField(
        choices=[c.value for c in PosAngleConstraintMode],
        required=False,
        allow_blank=False,
    )
    posAngleConstraintAngleInput = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0, max_value=360.0
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Perform cross-field validation and build the structured data for the clone
        observation.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data dictionary.

        Returns
        -------
        dict[str, Any]
            The validated data dictionary.
        """
        # Assign observation ID and observing mode if provided.
        self._observation_id = data.get("hiddenObservationIdInput")
        self._observing_mode = data.get("hiddenObservingModeInput")

        mode = data.get("posAngleConstraintModeSelect")
        angle = data.get("posAngleConstraintAngleInput")

        # Validate that angle is provided if mode requires it.
        if mode in {
            PosAngleConstraintMode.FIXED.value,
            PosAngleConstraintMode.ALLOW_FLIP.value,
            PosAngleConstraintMode.PARALLACTIC_OVERRIDE.value,
        }:
            if angle is None:
                raise serializers.ValidationError(
                    {
                        "Position Angle Input": (
                            "This angle is required for the selected mode."
                        )
                    }
                )

        return {
            "observerNotes": data.get("observerNotesTextarea"),
            "constraintSet": {
                "imageQuality": data.get("imageQualitySelect"),
                "cloudExtinction": data.get("cloudExtinctionSelect"),
                "skyBackground": data.get("skyBackgroundSelect"),
                "waterVapor": data.get("waterVaporSelect"),
                # Placeholder for other serializer field.
                "elevationRange": None,
            },
            "posAngleConstraint": {
                "mode": mode,
                "angle": {"degrees": angle},
            },
            # Placeholder for other serializer field.
            "observingMode": None,
            "scienceRequirements": {"exposureTimeMode": None},
        }

    @property
    def observation_id(self) -> str | None:
        return getattr(self, "_observation_id", None)

    @property
    def observing_mode(self) -> str | None:
        return getattr(self, "_observing_mode", None)
