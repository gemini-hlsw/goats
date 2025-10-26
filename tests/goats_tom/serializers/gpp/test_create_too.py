import pytest
from rest_framework.exceptions import ValidationError
from tom_targets.models import BaseTarget
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.serializers.gpp.create_too import CreateTooSerializer


@pytest.mark.django_db
class TestCreateTooSerializer:
    """Tests for CreateTooSerializer."""

    @pytest.fixture
    def target(self) -> BaseTarget:
        """Create a Sidereal target instance."""
        return SiderealTargetFactory(ra=150.123, dec=-20.456)

    def test_valid_data(self, target: BaseTarget) -> None:
        """Test serializer with all required fields present."""
        data = {
            "hiddenGoatsTargetIdInput": target.pk,
            "hiddenTargetIdInput": "gpp-target-123",
            "hiddenObservationIdInput": "gpp-observation-456",
            "hiddenObservingModeInput": "GMOS_NORTH_LONG_SLIT",
        }

        serializer = CreateTooSerializer(data=data)
        assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"

        assert serializer.goats_target == target
        assert serializer.gpp_target_id == "gpp-target-123"
        assert serializer.gpp_observation_id == "gpp-observation-456"
        assert serializer.instrument == "GMOS_NORTH_LONG_SLIT"

    @pytest.mark.parametrize(
        "invalid_data,missing_field",
        [
            ({}, "hiddenGoatsTargetIdInput"),
            (
                {
                    "hiddenTargetIdInput": "target-id",
                    "hiddenObservationIdInput": "obs-id",
                },
                "hiddenGoatsTargetIdInput",
            ),
            (
                {"hiddenGoatsTargetIdInput": 1, "hiddenObservationIdInput": "obs-id"},
                "hiddenTargetIdInput",
            ),
            (
                {"hiddenGoatsTargetIdInput": 1, "hiddenTargetIdInput": "target-id"},
                "hiddenObservationIdInput",
            ),
            (
                {
                    "hiddenGoatsTargetIdInput": 1,
                    "hiddenTargetIdInput": "",
                    "hiddenObservationIdInput": "obs-id",
                },
                "hiddenTargetIdInput",
            ),
        ],
    )
    def test_invalid_data(self, invalid_data: dict, missing_field: str) -> None:
        """Test that serializer rejects missing or invalid required fields."""
        serializer = CreateTooSerializer(data=invalid_data)
        assert not serializer.is_valid(), "Serializer should fail validation."
        assert missing_field in serializer.errors, (
            f"Missing expected error for '{missing_field}'"
        )

    def test_invalid_target_reference(self) -> None:
        """Test that invalid PK raises error on goats target lookup."""
        data = {
            "hiddenGoatsTargetIdInput": 99999,  # Assuming this PK doesn't exist
            "hiddenTargetIdInput": "gpp-target-999",
            "hiddenObservationIdInput": "gpp-observation-999",
        }

        serializer = CreateTooSerializer(data=data)
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
