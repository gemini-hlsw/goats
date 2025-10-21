import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import CloneObservationSerializer
from gpp_client.api.enums import (
    ImageQualityPreset,
    CloudExtinctionPreset,
    SkyBackground,
    WaterVapor,
    PosAngleConstraintMode,
)


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # All fields present and valid, angle mode that requires angle.
        (
            {
                "hiddenObservationIdInput": "obs123",
                "hiddenObservingModeInput": "GMOS",
                "observerNotesTextarea": "Testing full input.",
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.DARK.value,
                "waterVaporSelect": WaterVapor.DRY.value,
                "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
                "posAngleConstraintAngleInput": "180.0",
            },
            {
                "observerNotes": "Testing full input.",
                "constraintSet": {
                    "imageQuality": ImageQualityPreset.ONE_POINT_FIVE.value,
                    "cloudExtinction": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                    "skyBackground": SkyBackground.DARK.value,
                    "waterVapor": WaterVapor.DRY.value,
                    "elevationRange": None,
                },
                "posAngleConstraint": {
                    "mode": PosAngleConstraintMode.FIXED.value,
                    "angle": {"degrees": 180.0},
                },
                "observingMode": None,
            },
        ),
        # Angle not required for selected mode.
        (
            {
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.BRIGHT.value,
                "waterVaporSelect": WaterVapor.DRY.value,
                "posAngleConstraintModeSelect": PosAngleConstraintMode.UNBOUNDED.value,
            },
            {
                "observerNotes": None,
                "constraintSet": {
                    "imageQuality": ImageQualityPreset.ONE_POINT_FIVE.value,
                    "cloudExtinction": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                    "skyBackground": SkyBackground.BRIGHT.value,
                    "waterVapor": WaterVapor.DRY.value,
                    "elevationRange": None,
                },
                "posAngleConstraint": {
                    "mode": PosAngleConstraintMode.UNBOUNDED.value,
                    "angle": {"degrees": None},
                },
                "observingMode": None,
            },
        ),
        # All optional fields blank strings.
        (
            {
                "hiddenObservationIdInput": "",
                "hiddenObservingModeInput": "",
                "observerNotesTextarea": "",
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.GRAY.value,
                "waterVaporSelect": WaterVapor.DRY.value,
                "posAngleConstraintModeSelect": PosAngleConstraintMode.AVERAGE_PARALLACTIC.value,
            },
            {
                "observerNotes": None,
                "constraintSet": {
                    "imageQuality": ImageQualityPreset.ONE_POINT_FIVE.value,
                    "cloudExtinction": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                    "skyBackground": SkyBackground.GRAY.value,
                    "waterVapor": WaterVapor.DRY.value,
                    "elevationRange": None,
                },
                "posAngleConstraint": {
                    "mode": PosAngleConstraintMode.AVERAGE_PARALLACTIC.value,
                    "angle": {"degrees": None},
                },
                "observingMode": None,
            },
        ),
    ],
)
def test_valid_clone_observation_inputs(input_data, expected_output):
    """Test valid combinations of CloneObservationSerializer input."""
    serializer = CloneObservationSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == expected_output


@pytest.mark.parametrize(
    "input_data, expected_error_field, expected_message",
    [
        # Angle required but missing.
        (
            {
                "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.DARK.value,
                "waterVaporSelect": WaterVapor.DRY.value,
            },
            "Position Angle Input",
            "This angle is required for the selected mode.",
        ),
        # Angle required but null.
        (
            {
                "posAngleConstraintModeSelect": PosAngleConstraintMode.ALLOW_FLIP.value,
                "posAngleConstraintAngleInput": None,
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.DARK.value,
                "waterVaporSelect": WaterVapor.DRY.value,
            },
            "Position Angle Input",
            "This angle is required for the selected mode.",
        ),
        # Angle out of bounds.
        (
            {
                "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
                "posAngleConstraintAngleInput": "999.0",
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.DARK.value,
                "waterVaporSelect": WaterVapor.DRY.value,
            },
            "posAngleConstraintAngleInput",
            "Ensure this value is less than or equal to 360.0.",
        ),
        (
            {
                "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
                "posAngleConstraintAngleInput": "-10.0",
                "imageQualitySelect": ImageQualityPreset.ONE_POINT_FIVE.value,
                "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
                "skyBackgroundSelect": SkyBackground.DARK.value,
                "waterVaporSelect": WaterVapor.DRY.value,
            },
            "posAngleConstraintAngleInput",
            "Ensure this value is greater than or equal to 0.0.",
        ),
    ],
)
def test_invalid_clone_observation_inputs(input_data, expected_error_field, expected_message):
    """Test invalid CloneObservationSerializer cases."""
    serializer = CloneObservationSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    error_str = str(excinfo.value.detail)
    assert expected_error_field in error_str
    assert expected_message in error_str
