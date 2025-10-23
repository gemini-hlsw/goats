import pytest
from gpp_client.api.enums import (
    CloudExtinctionPreset,
    ImageQualityPreset,
    SkyBackground,
    WaterVapor,
)
from gpp_client.api.input_types import ConstraintSetInput

from goats_tom.serializers.gpp.constraint_set import ConstraintSetSerializer


@pytest.mark.django_db
class TestConstraintSetSerializer:
    """Tests for ConstraintSetSerializer."""

    @pytest.fixture
    def valid_data(self) -> dict:
        return {
            "imageQualitySelect": ImageQualityPreset.POINT_EIGHT.value,
            "cloudExtinctionSelect": CloudExtinctionPreset.POINT_THREE.value,
            "skyBackgroundSelect": SkyBackground.GRAY.value,
            "waterVaporSelect": WaterVapor.MEDIAN.value,
            "airMassMinimumInput": 1.0,
            "airMassMaximumInput": 2.0,
            "elevationRangeSelect": "Air Mass",
        }

    def test_valid_constraint_set(self, valid_data: dict) -> None:
        """Test valid input data."""
        serializer = ConstraintSetSerializer(data=valid_data)
        assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"

        # Validate internal state
        assert (
            serializer.validated_data["imageQualitySelect"]
            == ImageQualityPreset.POINT_EIGHT.value
        )

    def test_format_gpp(self, valid_data: dict) -> None:
        """Test that format_gpp returns correctly structured dict."""
        serializer = ConstraintSetSerializer(data=valid_data)
        assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"
        formatted = serializer.format_gpp()

        assert formatted == {
            "imageQuality": "POINT_EIGHT",
            "cloudExtinction": "POINT_THREE",
            "skyBackground": "GRAY",
            "waterVapor": "MEDIAN",
            "elevationRange": {
                "airMass": {
                    "min": 1.0,
                    "max": 2.0,
                }
            },
        }

    def test_to_pydantic(self, valid_data: dict) -> None:
        """Test serializer output as a Pydantic ConstraintSetInput model."""
        serializer = ConstraintSetSerializer(data=valid_data)
        assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"
        model = serializer.to_pydantic()

        assert isinstance(model, ConstraintSetInput)
        assert model.image_quality == ImageQualityPreset.POINT_EIGHT
        assert model.cloud_extinction == CloudExtinctionPreset.POINT_THREE
        assert model.sky_background == SkyBackground.GRAY
        assert model.water_vapor == WaterVapor.MEDIAN
        assert model.elevation_range.air_mass.min == 1.0
        assert model.elevation_range.air_mass.max == 2.0

    @pytest.mark.parametrize(
        "field,invalid_value",
        [
            ("imageQualitySelect", "INVALID_IQ"),
            ("cloudExtinctionSelect", "NOT_A_CLOUD"),
            ("skyBackgroundSelect", "BRIGHTEST"),
            ("waterVaporSelect", "SUPER_WET"),
        ],
    )
    def test_invalid_enum_choices(
        self, valid_data: dict, field: str, invalid_value: str
    ) -> None:
        """Test invalid enum values raise validation errors."""
        valid_data[field] = invalid_value
        serializer = ConstraintSetSerializer(data=valid_data)
        assert not serializer.is_valid()
        assert field in serializer.errors
