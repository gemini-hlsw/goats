import pytest
from gpp_client.api.enums import PosAngleConstraintMode
from gpp_client.api.input_types import AngleInput, PosAngleConstraintInput
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.pos_angle import PosAngleSerializer


class TestPosAngleSerializer:
    """Tests for PosAngleSerializer."""

    @pytest.mark.parametrize(
        "mode,angle,should_be_valid",
        [
            # Required angle modes with valid angles.
            (PosAngleConstraintMode.FIXED.value, 45.0, True),
            (PosAngleConstraintMode.ALLOW_FLIP.value, 180.0, True),
            (PosAngleConstraintMode.PARALLACTIC_OVERRIDE.value, 0.0, True),
            # Required angle modes missing angle.
            (PosAngleConstraintMode.FIXED.value, None, False),
            (PosAngleConstraintMode.ALLOW_FLIP.value, None, False),
            (PosAngleConstraintMode.PARALLACTIC_OVERRIDE.value, None, False),
            # Non-required angle modes without angle.
            (PosAngleConstraintMode.AVERAGE_PARALLACTIC.value, None, True),
            (PosAngleConstraintMode.UNBOUNDED.value, None, True),
            # Non-required modes with optional angle.
            (PosAngleConstraintMode.AVERAGE_PARALLACTIC.value, 120.5, True),
            (PosAngleConstraintMode.UNBOUNDED.value, 250.0, True),
            # Angle out of bounds.
            (PosAngleConstraintMode.FIXED.value, -1.0, False),
            (PosAngleConstraintMode.FIXED.value, 361.0, False),
        ],
    )
    def test_validation_cases(self, mode, angle, should_be_valid):
        """Test PosAngleSerializer validation logic for all angle-mode combinations."""
        data = {
            "posAngleConstraintModeSelect": mode,
            "posAngleConstraintAngleInput": angle,
        }
        serializer = PosAngleSerializer(data=data)

        if should_be_valid:
            assert serializer.is_valid(), (
                f"Expected valid for mode={mode}, angle={angle}, got {serializer.errors}"
            )
        else:
            assert not serializer.is_valid(), (
                f"Expected invalid for mode={mode}, angle={angle}"
            )

    def test_missing_mode_is_invalid(self):
        """Test that missing required mode field raises validation error."""
        serializer = PosAngleSerializer(data={"posAngleConstraintAngleInput": 45.0})
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert "posAngleConstraintModeSelect" in excinfo.value.detail
        assert "This field is required." in str(
            excinfo.value.detail["posAngleConstraintModeSelect"][0]
        )

    @pytest.mark.parametrize(
        "mode",
        [
            PosAngleConstraintMode.FIXED.value,
            PosAngleConstraintMode.ALLOW_FLIP.value,
            PosAngleConstraintMode.PARALLACTIC_OVERRIDE.value,
        ],
    )
    def test_raises_validation_error_when_angle_required_missing(self, mode):
        """Ensure ValidationError is raised when angle is missing for required modes."""
        data = {"posAngleConstraintModeSelect": mode}
        serializer = PosAngleSerializer(data=data)
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert "posAngleConstraintAngleInput" in excinfo.value.detail
        assert "Angle is required for the selected mode." in str(
            excinfo.value.detail["posAngleConstraintAngleInput"][0]
        )

    def test_format_gpp_with_angle(self):
        """Test that format_gpp() correctly formats output when angle is present."""
        data = {
            "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
            "posAngleConstraintAngleInput": 180.0,
        }
        serializer = PosAngleSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        expected = {
            "mode": PosAngleConstraintMode.FIXED.value,
            "angle": {"degrees": 180.0},
        }
        assert serializer.format_gpp() == expected, (
            "Formatted GPP output mismatch when angle provided."
        )

    def test_format_gpp_without_angle(self):
        """Test that format_gpp() omits angle when not provided."""
        data = {
            "posAngleConstraintModeSelect": PosAngleConstraintMode.UNBOUNDED.value,
        }
        serializer = PosAngleSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        expected = {"mode": PosAngleConstraintMode.UNBOUNDED.value}
        assert serializer.format_gpp() == expected, (
            "Angle should be omitted when not provided."
        )

    from gpp_client.api.input_types import PosAngleConstraintInput

    def test_to_pydantic_model_valid_output(self):
        """Test that to_pydantic() returns a valid PosAngleConstraintInput model."""
        data = {
            "posAngleConstraintModeSelect": PosAngleConstraintMode.FIXED.value,
            "posAngleConstraintAngleInput": 270.0,
        }
        serializer = PosAngleSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        model = serializer.to_pydantic()
        assert isinstance(model, PosAngleConstraintInput)
        assert model.mode == PosAngleConstraintMode.FIXED.value
        assert model.angle == AngleInput(**{"degrees": 270.0})

    def test_to_pydantic_model_without_angle(self):
        """Test that to_pydantic() works when angle is not provided."""
        data = {
            "posAngleConstraintModeSelect": PosAngleConstraintMode.UNBOUNDED.value,
        }
        serializer = PosAngleSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        model = serializer.to_pydantic()
        assert isinstance(model, PosAngleConstraintInput)
        assert model.mode == PosAngleConstraintMode.UNBOUNDED.value
        assert model.angle is None
