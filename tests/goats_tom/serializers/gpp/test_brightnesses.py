import pytest
from rest_framework.serializers import ValidationError

from goats_tom.serializers.gpp.brightnesses import (
    BrightnessesSerializer,
    BrightnessSerializer,
)
from gpp_client.api.enums import Band, BrightnessIntegratedUnits


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Test case: Valid input data with multiple brightnesses.
        (
            {
                "brightnessValueInput1": "10.5",
                "brightnessBandSelect1": Band.SLOAN_G.value,
                "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                "brightnessValueInput2": "20.0",
                "brightnessBandSelect2": Band.SLOAN_R.value,
                "brightnessUnitsSelect2": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
            },
            {
                "brightnesses": [
                    {
                        "band": Band.SLOAN_G.value,
                        "value": 10.5,
                        "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                    },
                    {
                        "band": Band.SLOAN_R.value,
                        "value": 20.0,
                        "units": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
                    },
                ]
            },
        ),
        # Test case: Empty input data returns None.
        ({}, {"brightnesses": None}),
        # Test case: Single brightness entry.
        (
            {
                "brightnessValueInput1": "15.0",
                "brightnessBandSelect1": Band.H.value,
                "brightnessUnitsSelect1": BrightnessIntegratedUnits.JANSKY.value,
            },
            {
                "brightnesses": [
                    {
                        "band": Band.H.value,
                        "value": 15.0,
                        "units": BrightnessIntegratedUnits.JANSKY.value,
                    }
                ]
            },
        ),
        # Test case: Brightness index out of order and skipping.
        (
            {
                "brightnessValueInput1": ["21"],
                "brightnessBandSelect1": [Band.SLOAN_G.value],
                "brightnessUnitsSelect1": [BrightnessIntegratedUnits.AB_MAGNITUDE.value],
                "brightnessValueInput3": ["22"],
                "brightnessBandSelect3": [Band.SLOAN_R.value],
                "brightnessUnitsSelect3": [BrightnessIntegratedUnits.AB_MAGNITUDE.value],
            },
            {
                "brightnesses": [
                    {
                        "band": Band.SLOAN_G.value,
                        "value": 21.0,
                        "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                    },
                    {
                        "band": Band.SLOAN_R.value,
                        "value": 22.0,
                        "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                    },
                ]
            },
        ),
    ],
)
def test_to_internal_value_valid(input_data, expected_output):
    """Test valid inputs for BrightnessesSerializer."""
    serializer = BrightnessesSerializer()
    result = serializer.to_internal_value(input_data)
    assert result == expected_output


@pytest.mark.parametrize(
    "input_data, expected_exception_message",
    [
        # Test case: Missing value input.
        (
            {
                "brightnessBandSelect1": Band.SLOAN_G.value,
                "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
            },
            "A Brightness value is not a valid number.",
        ),
        # Test case: Missing band.
        (
            {
                "brightnessValueInput1": "10.5",
                "brightnessUnitsSelect1": BrightnessIntegratedUnits.JANSKY.value,
            },
            "A Brightness is missing a band or units.",
        ),
        # Test case: Missing unit.
        (
            {
                "brightnessValueInput1": "10.5",
                "brightnessBandSelect1": Band.SLOAN_G.value,
            },
            "A Brightness is missing a band or units.",
        ),
        # Test case: Invalid value input.
        (
            {
                "brightnessValueInput1": "invalid",
                "brightnessBandSelect1": Band.SLOAN_G.value,
                "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
            },
            "A Brightness value is not a valid number.",
        ),
    ],
)
def test_to_internal_value_invalid(input_data, expected_exception_message):
    """Test invalid inputs for BrightnessesSerializer."""
    serializer = BrightnessesSerializer()
    with pytest.raises(ValidationError) as excinfo:
        serializer.to_internal_value(input_data)
    assert str(excinfo.value.detail[0]) == expected_exception_message


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        (
            {
                "band": Band.SLOAN_G.value,
                "value": 21.0,
                "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
            },
            {
                "band": Band.SLOAN_G.value,
                "value": 21.0,
                "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
            },
        ),
        (
            {
                "band": Band.J.value,
                "value": 19.5,
                "units": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
            },
            {
                "band": Band.J.value,
                "value": 19.5,
                "units": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
            },
        ),
    ],
)
def test_brightness_serializer_valid(input_data, expected_output):
    """Test valid inputs for BrightnessSerializer."""
    serializer = BrightnessSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == expected_output


@pytest.mark.parametrize(
    "input_data, missing_field",
    [
        (
            {"value": 21.0, "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value},
            "band",
        ),
        (
            {"band": Band.SLOAN_G.value, "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value},
            "value",
        ),
        (
            {"band": Band.SLOAN_G.value, "value": 21.0},
            "units",
        ),
    ],
)
def test_brightness_serializer_missing_field(input_data, missing_field):
    """Test BrightnessSerializer with missing required fields."""
    serializer = BrightnessSerializer(data=input_data)
    assert not serializer.is_valid()
    assert missing_field in serializer.errors


@pytest.mark.parametrize(
    "input_data, invalid_field",
    [
        ({"band": "INVALID", "value": 21.0, "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value}, "band"),
        ({"band": Band.SLOAN_G.value, "value": 21.0, "units": "BAD_UNIT"}, "units"),
    ],
)
def test_brightness_serializer_partial_invalid_enum(input_data, invalid_field):
    """Test BrightnessSerializer when one enum field is invalid."""
    serializer = BrightnessSerializer(data=input_data)
    assert not serializer.is_valid()
    assert invalid_field in serializer.errors
    assert "is not a valid choice" in str(serializer.errors[invalid_field][0])
