import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.instruments import GMOSNorthLongSlitSerializer


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # All fields valid.
        (
            {
                "centralWavelengthInput": "750.5",
                "wavelengthDithersInput": "0.0, 8.0, -8.0",
                "spatialOffsetsInput": "0.0, 15.0, -15.0",
            },
            {
                "gmos_north_long_slit": {
                    "centralWavelength": {"nanometers": 750.5},
                    "explicitWavelengthDithers": [
                        {"nanometers": 0.0},
                        {"nanometers": 8.0},
                        {"nanometers": -8.0},
                    ],
                    "explicitOffsets": [
                        {"arcseconds": 0.0},
                        {"arcseconds": 15.0},
                        {"arcseconds": -15.0},
                    ],
                }
            },
        ),
        # Only central wavelength.
        (
            {"centralWavelengthInput": "700.0"},
            {
                "gmos_north_long_slit": {
                    "centralWavelength": {"nanometers": 700.0}
                }
            },
        ),
        # Only dithers.
        (
            {"wavelengthDithersInput": "1.0, 2.0"},
            {
                "gmos_north_long_slit": {
                    "explicitWavelengthDithers": [
                        {"nanometers": 1.0},
                        {"nanometers": 2.0},
                    ]
                }
            },
        ),
        # Only spatial offsets.
        (
            {"spatialOffsetsInput": "5.5, -5.5"},
            {
                "gmos_north_long_slit": {
                    "explicitOffsets": [
                        {"arcseconds": 5.5},
                        {"arcseconds": -5.5},
                    ]
                }
            },
        ),
        # Input with extra whitespace or empty entries.
        (
            {
                "wavelengthDithersInput": " 1.0 , , 2.0 ",
                "spatialOffsetsInput": " , 10.0 , -10.0",
            },
            {
                "gmos_north_long_slit": {
                    "explicitWavelengthDithers": [
                        {"nanometers": 1.0},
                        {"nanometers": 2.0},
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
def test_valid_gmos_north_longslit_inputs(input_data, expected_output):
    """Test valid GMOS North Long Slit input cases."""
    serializer = GMOSNorthLongSlitSerializer()
    result = serializer.validate(input_data)
    assert result == expected_output


@pytest.mark.parametrize(
    "input_data, expected_message",
    [
        (
            {"centralWavelengthInput": "not_a_number"},
            "centralWavelengthInput must be a numeric value in nanometers.",
        ),
        (
            {"wavelengthDithersInput": "1.0, not_a_number"},
            "wavelengthDithersInput must be a comma-separated list of numeric values in nanometers.",
        ),
        (
            {"spatialOffsetsInput": "0.0, fail"},
            "spatialOffsetsInput must be a comma-separated list of numeric values in arcseconds.",
        ),
    ],
)
def test_invalid_gmos_north_longslit_inputs(input_data, expected_message):
    """Test invalid GMOS North Long Slit input cases."""
    serializer = GMOSNorthLongSlitSerializer()
    with pytest.raises(ValidationError) as excinfo:
        serializer.validate(input_data)
    assert expected_message in str(excinfo.value.detail[0])
