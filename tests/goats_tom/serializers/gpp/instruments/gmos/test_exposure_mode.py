import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.instruments.gmos.exposure_mode import (
    ExposureModeSerializer,
)


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Valid Signal-to-Noise mode.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": 10.5,
                "snWavelengthInput": 500.0,
            },
            {
                "signalToNoise": {
                    "value": 10.5,
                    "at": {"nanometers": 500.0},
                }
            },
        ),
        # Valid Time & Count mode.
        (
            {
                "exposureModeSelect": "Time & Count",
                "exposureTimeInput": 2.5,
                "numExposuresInput": 3,
                "countWavelengthInput": 600.0,
            },
            {
                "timeAndCount": {
                    "time": {"seconds": 2.5},
                    "count": 3,
                    "at": {"nanometers": 600.0},
                }
            },
        ),
    ],
)
def test_format_gpp_valid_modes(input_data, expected_output):
    """Test correct GPP formatting for valid exposure modes."""
    serializer = ExposureModeSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    formatted = serializer.format_gpp()
    assert formatted == expected_output


@pytest.mark.parametrize(
    "input_data, expected_message",
    [
        # Missing snInput.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snWavelengthInput": 500.0,
            },
            "Both S/N value and wavelength are required for Signal / Noise mode.",
        ),
        # Missing snWavelengthInput.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": 10.5,
            },
            "Both S/N value and wavelength are required for Signal / Noise mode.",
        ),
        # Missing exposureTimeInput.
        (
            {
                "exposureModeSelect": "Time & Count",
                "numExposuresInput": 3,
                "countWavelengthInput": 600.0,
            },
            "Exposure time, number of exposures, and wavelength are required for Time & Count mode.",
        ),
        # Missing numExposuresInput.
        (
            {
                "exposureModeSelect": "Time & Count",
                "exposureTimeInput": 2.5,
                "countWavelengthInput": 600.0,
            },
            "Exposure time, number of exposures, and wavelength are required for Time & Count mode.",
        ),
        # Invalid mode.
        (
            {"exposureModeSelect": "Invalid Mode"},
            '"Invalid Mode" is not a valid choice.',
        ),
    ],
)
def test_validate_invalid_modes(input_data, expected_message):
    """Test validation errors for missing or invalid exposure mode data."""
    serializer = ExposureModeSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)
    assert expected_message in str(excinfo.value)


def test_to_pydantic_returns_valid_model():
    """Test to_pydantic() produces a valid ExposureTimeModeInput model."""
    input_data = {
        "exposureModeSelect": "Signal / Noise",
        "snInput": 15.0,
        "snWavelengthInput": 700.0,
    }

    serializer = ExposureModeSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors

    model = serializer.to_pydantic()
    from gpp_client.api.input_types import ExposureTimeModeInput

    assert isinstance(model, ExposureTimeModeInput)
    assert model.signal_to_noise.value == 15.0
    assert model.signal_to_noise.at.nanometers == 700.0
