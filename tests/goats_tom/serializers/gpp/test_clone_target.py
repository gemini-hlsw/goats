import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import CloneTargetSerializer


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # All fields provided and valid.
        (
            {
                "hiddenTargetIdInput": "TGT-123",
                "radialVelocityInput": "12.5",
                "parallaxInput": "3.14",
                "uRaInput": "-1.5",
                "uDecInput": "2.7",
            },
            {
                "sidereal": {
                    "radialVelocity": {"kilometersPerSecond": 12.5},
                    "parallax": {"milliarcseconds": 3.14},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": -1.5},
                        "dec": {"milliarcsecondsPerYear": 2.7},
                    },
                    "ra": {"degrees": None},
                    "dec": {"degrees": None},
                    "epoch": "J2000",
                },
                "sourceProfile": None,
            },
        ),
        # Only radial velocity.
        (
            {"radialVelocityInput": "20.0"},
            {
                "sidereal": {
                    "radialVelocity": {"kilometersPerSecond": 20.0},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": None},
                    "dec": {"degrees": None},
                    "epoch": "J2000",
                },
                "sourceProfile": None,
            },
        ),
        # All optional fields blank strings.
        (
            {
                "hiddenTargetIdInput": "",
                "radialVelocityInput": "",
                "parallaxInput": "",
                "uRaInput": "",
                "uDecInput": "",
            },
            {
                "sidereal": {
                    "radialVelocity": {"kilometersPerSecond": None},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": None},
                    "dec": {"degrees": None},
                    "epoch": "J2000",
                },
                "sourceProfile": None,
            },
        ),
        # No fields provided.
        (
            {},
            {
                "sidereal": {
                    "radialVelocity": {"kilometersPerSecond": None},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": None},
                    "dec": {"degrees": None},
                    "epoch": "J2000",
                },
                "sourceProfile": None,
            },
        ),
        # Not used field provided.
        (
            {"someUnusedField": "value"},
            {
                "sidereal": {
                    "radialVelocity": {"kilometersPerSecond": None},
                    "parallax": {"milliarcseconds": None},
                    "properMotion": {
                        "ra": {"milliarcsecondsPerYear": None},
                        "dec": {"milliarcsecondsPerYear": None},
                    },
                    "ra": {"degrees": None},
                    "dec": {"degrees": None},
                    "epoch": "J2000",
                },
                "sourceProfile": None,
            },
        ),
    ],
)
def test_valid_clone_target_inputs(input_data, expected_output):
    """Test valid CloneTargetSerializer cases with formdata string inputs."""
    serializer = CloneTargetSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == expected_output


@pytest.mark.parametrize(
    "input_data, expected_error_field",
    [
        ({"radialVelocityInput": "not_a_number"}, "radialVelocityInput"),
        ({"parallaxInput": "NaNish"}, "parallaxInput"),
        ({"uRaInput": "oops"}, "uRaInput"),
        ({"uDecInput": "?"}, "uDecInput"),
    ],
)
def test_invalid_clone_target_inputs(input_data, expected_error_field):
    """Test invalid CloneTargetSerializer input where numeric coercion fails."""
    serializer = CloneTargetSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    assert expected_error_field in excinfo.value.detail
