import pytest
from rest_framework.exceptions import ValidationError
from tom_targets.models import BaseTarget
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.serializers.gpp import SiderealSerializer


@pytest.mark.django_db
class TestSiderealSerializer:
    @pytest.fixture
    def target(self) -> BaseTarget:
        return SiderealTargetFactory(ra=150.123, dec=-20.456)

    @pytest.mark.parametrize(
        "input_data, expected_output",
        [
            # All fields present and valid.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "radialVelocityInput": "12.5",
                    "parallaxInput": "3.14",
                    "uRaInput": "-1.5",
                    "uDecInput": "2.7",
                },
                lambda t: {
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000.000",
                    "radialVelocity": {"kilometersPerSecond": 12.5},
                    "parallax": {"milliarcseconds": 3.14},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": -1.5},
                        "dec": {"milliarcsecondsPerYear": 2.7},
                    },
                },
            ),
            # Only radial velocity provided.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "radialVelocityInput": "10.0",
                },
                lambda t: {
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000.000",
                    "radialVelocity": {"kilometersPerSecond": 10.0},
                },
            ),
            # Optional fields.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "radialVelocityInput": None,
                    "parallaxInput": None,
                    "uRaInput": None,
                    "uDecInput": None,
                },
                lambda t: {
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000.000",
                },
            ),
            # Extra unused field present.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "someUnusedField": "unused",
                },
                lambda t: {
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000.000",
                },
            ),
        ],
    )
    def test_valid_inputs(self, target, input_data, expected_output):
        """
        Test that valid sidereal inputs produce the correct formatted GPP dictionary.
        """
        serializer = SiderealSerializer(data=input_data(target))
        assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"
        assert serializer.format_gpp() == expected_output(target), (
            "GPP output mismatch."
        )
        assert serializer.target == target, "Target instance mismatch."

    @pytest.mark.parametrize(
        "input_data, expected_error_field",
        [
            ({"hiddenGoatsTargetIdInput": None}, "hiddenGoatsTargetIdInput"),
            ({"hiddenGoatsTargetIdInput": ""}, "hiddenGoatsTargetIdInput"),
            (
                {"hiddenGoatsTargetIdInput": "9999"},
                "hiddenGoatsTargetIdInput",
            ),  # Nonexistent PK
            ({"radialVelocityInput": "fast"}, "radialVelocityInput"),
            ({"parallaxInput": "oops"}, "parallaxInput"),
            ({"uRaInput": "n/a"}, "uRaInput"),
            ({"uDecInput": "!@#"}, "uDecInput"),
        ],
    )
    def test_invalid_inputs(self, input_data, expected_error_field):
        """
        Test that invalid input values raise ValidationError for the correct field.
        """
        serializer = SiderealSerializer(data=input_data)
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert expected_error_field in excinfo.value.detail, (
            "Expected error field missing."
        )

    def test_target_property_returns_instance(self, target):
        """
        Test that the `target` property returns the expected Target instance.
        """
        serializer = SiderealSerializer(
            data={"hiddenGoatsTargetIdInput": str(target.id)}
        )
        assert serializer.is_valid(), (
            f"Unexpected validation errors: {serializer.errors}"
        )
        assert serializer.target == target, "Incorrect target property returned."
