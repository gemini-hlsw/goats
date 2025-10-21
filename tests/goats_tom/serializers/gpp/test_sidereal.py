import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import SiderealSerializer
from tom_targets.models import BaseTarget
from tom_targets.tests.factories import SiderealTargetFactory


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
                    "radialVelocity": {"kilometersPerSecond": 12.5},
                    "parallax": {"milliarcseconds": 3.14},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": -1.5},
                        "dec": {"milliarcsecondsPerYear": 2.7},
                    },
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000",
                },
            ),
            # Some fields missing.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "radialVelocityInput": "10.0",
                },
                lambda t: {
                    "radialVelocity": {"kilometersPerSecond": 10.0},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000",
                },
            ),
            # Optional fields blank.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "radialVelocityInput": "",
                    "parallaxInput": "",
                    "uRaInput": "",
                    "uDecInput": "",
                },
                lambda t: {
                    "radialVelocity": {"kilometersPerSecond": None},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000",
                },
            ),
            # Extra unused field.
            (
                lambda t: {
                    "hiddenGoatsTargetIdInput": str(t.id),
                    "someUnusedField": "whatever",
                },
                lambda t: {
                    "radialVelocity": {"kilometersPerSecond": None},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": t.ra},
                    "dec": {"degrees": t.dec},
                    "epoch": "J2000",
                },
            ),
        ],
    )
    def test_valid_inputs(self, target, input_data, expected_output):
        serializer = SiderealSerializer(data=input_data(target))
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == expected_output(target)
        assert serializer.target == target

    @pytest.mark.parametrize(
        "input_data, expected_error_field",
        [
            ({"hiddenGoatsTargetIdInput": None}, "hiddenGoatsTargetIdInput"),
            ({"hiddenGoatsTargetIdInput": ""}, "hiddenGoatsTargetIdInput"),
            ({"hiddenGoatsTargetIdInput": "9999"}, "hiddenGoatsTargetIdInput"),  # non-existent PK
            ({"radialVelocityInput": "fast"}, "radialVelocityInput"),
            ({"parallaxInput": "nope"}, "parallaxInput"),
            ({"uRaInput": "x"}, "uRaInput"),
            ({"uDecInput": "?"}, "uDecInput"),
        ],
    )
    def test_invalid_inputs(self, input_data, expected_error_field):
        serializer = SiderealSerializer(data=input_data)
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert expected_error_field in excinfo.value.detail

    def test_property_target_exposed(self, target):
        serializer = SiderealSerializer(data={"hiddenGoatsTargetIdInput": str(target.id)})
        assert serializer.is_valid()
        assert serializer.target == target
