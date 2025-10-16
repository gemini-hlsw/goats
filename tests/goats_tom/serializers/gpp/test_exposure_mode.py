import pytest
from rest_framework.exceptions import ValidationError
from goats_tom.serializers.gpp.exposure_mode import GPPExposureModeSerializer

@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Test Signal-to-Noise Mode with valid inputs.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": "10.5",
                "snWavelengthInput": "500",
            },
            {
                "signalToNoise": {
                    "value": 10.5,
                    "at": {"nanometers": 500.0},
                }
            },
        ),
        # Test Fixed Exposure Mode with valid inputs.
        (
            {
                "exposureModeSelect": "Fixed Exposure",
                "exposureTimeInput": "2.5",
                "numExposuresInput": "3",
                "countWavelengthInput": "600",
            },
            {
                "timeAndCount": {
                    "time": {"seconds": 2.5},
                    "count": 3,
                    "at": {"nanometers": 600.0},
                }
            },
        ),
        # Test providing all inputs, ensuring correct mode is processed.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": "15.0",
                "snWavelengthInput": "700",
                "exposureTimeInput": "5.0",
                "numExposuresInput": "4",
                "countWavelengthInput": "800",
            },
            {
                "signalToNoise": {
                    "value": 15.0,
                    "at": {"nanometers": 700.0},
                }
            },
        ),
    ],
)
def test_validate_valid_inputs(input_data, expected_output):
    serializer = GPPExposureModeSerializer()
    assert serializer.validate(input_data) == expected_output


@pytest.mark.parametrize(
    "input_data, expected_exception_message",
    [
        # Test Signal-to-Noise Mode with missing inputs.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": "",
                "snWavelengthInput": "500",
            },
            "Missing signal-to-noise input(s).",
        ),
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": "10.5",
                "snWavelengthInput": "",
            },
            "Missing signal-to-noise input(s).",
        ),
        # Test Fixed Exposure Mode with missing inputs.
        (
            {
                "exposureModeSelect": "Fixed Exposure",
                "exposureTimeInput": "",
                "numExposuresInput": "3",
                "countWavelengthInput": "600",
            },
            "Missing fixed exposure input(s).",
        ),
        (
            {
                "exposureModeSelect": "Fixed Exposure",
                "exposureTimeInput": "2.5",
                "numExposuresInput": "",
                "countWavelengthInput": "600",
            },
            "Missing fixed exposure input(s).",
        ),
        # Test invalid exposure mode.
        (
            {
                "exposureModeSelect": "Invalid Mode",
            },
            "Invalid exposure mode selected.",
        ),
        # Test Signal-to-Noise Mode with non-numeric inputs.
        (
            {
                "exposureModeSelect": "Signal / Noise",
                "snInput": "abc",
                "snWavelengthInput": "500",
            },
            "Signal-to-noise values must be numeric.",
        ),
        # Test Fixed Exposure Mode with non-numeric inputs.
        (
            {
                "exposureModeSelect": "Fixed Exposure",
                "exposureTimeInput": "abc",
                "numExposuresInput": "3",
                "countWavelengthInput": "600",
            },
            "Fixed exposure values must be numeric.",
        ),
    ],
)
def test_validate_invalid_inputs(input_data, expected_exception_message):
    serializer = GPPExposureModeSerializer()
    with pytest.raises(ValidationError) as excinfo:
        serializer.validate(input_data)
    assert str(excinfo.value.detail[0]) == expected_exception_message
