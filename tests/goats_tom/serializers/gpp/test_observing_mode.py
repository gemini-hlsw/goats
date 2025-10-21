import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.observing_mode import ObservingModeSerializer
from gpp_client.api.enums import ObservingModeType


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        (
            # Valid GMOS South Long Slit input
            {
                "hiddenObservingModeInput": ObservingModeType.GMOS_SOUTH_LONG_SLIT.value,
                "centralWavelengthInput": "750.5",
                "wavelengthDithersInput": "0.0, 8.0",
                "spatialOffsetsInput": "10.0, -10.0",
            },
            {
                "gmos_south_long_slit": {
                    "centralWavelength": {"nanometers": 750.5},
                    "explicitWavelengthDithers": [
                        {"nanometers": 0.0},
                        {"nanometers": 8.0},
                    ],
                    "explicitOffsets": [
                        {"arcseconds": 10.0},
                        {"arcseconds": -10.0},
                    ],
                }
            },
        ),
    ],
)
def test_valid_observing_mode_inputs(input_data, expected_output):
    """Test valid observing mode input cases."""
    serializer = ObservingModeSerializer(data=input_data)
    assert serializer.is_valid()
    assert serializer.validated_data == expected_output


@pytest.mark.parametrize(
    "input_data, expected_error",
    [
        (
            # Invalid observing mode
            {"hiddenObservingModeInput": "INVALID_MODE"},
            '"INVALID_MODE" is not a valid choice.',
        ),
        (
            # Completely missing observing mode
            {},
            "This field is required.",
        ),
    ],
)
def test_invalid_observing_mode_inputs(input_data, expected_error):
    """Test invalid observing mode input cases."""
    serializer = ObservingModeSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)
    assert expected_error in str(excinfo.value.detail)
