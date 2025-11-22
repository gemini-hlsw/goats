import pytest
from gpp_client.api.enums import Band, BrightnessIntegratedUnits
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.source_profile.brightnesses import (
    BrightnessesSerializer,
    _BrightnessSerializer,
)


@pytest.mark.django_db
class TestBrightnessesSerializer:
    """Tests for BrightnessesSerializer and _BrightnessSerializer."""

    @pytest.mark.parametrize(
        "input_data, expected",
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
    def test_individual_valid(self, input_data, expected):
        """Test valid inputs for _BrightnessSerializer."""
        serializer = _BrightnessSerializer(data=input_data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == expected

    @pytest.mark.parametrize(
        "input_data, missing_field",
        [
            (
                {"value": 21.0, "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value},
                "band",
            ),
            (
                {
                    "band": Band.SLOAN_G.value,
                    "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                },
                "value",
            ),
            (
                {"band": Band.SLOAN_G.value, "value": 21.0},
                "units",
            ),
        ],
    )
    def test_individual_missing_field(self, input_data, missing_field):
        """Test missing required fields for _BrightnessSerializer."""
        serializer = _BrightnessSerializer(data=input_data)
        assert not serializer.is_valid()
        assert missing_field in serializer.errors

    @pytest.mark.parametrize(
        "input_data, invalid_field",
        [
            (
                {
                    "band": "INVALID",
                    "value": 21.0,
                    "units": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                },
                "band",
            ),
            (
                {
                    "band": Band.SLOAN_G.value,
                    "value": 21.0,
                    "units": "BAD_UNIT",
                },
                "units",
            ),
        ],
    )
    def test_individual_invalid_enum(self, input_data, invalid_field):
        """Test invalid enum choices for _BrightnessSerializer."""
        serializer = _BrightnessSerializer(data=input_data)
        assert not serializer.is_valid()
        assert invalid_field in serializer.errors
        assert "is not a valid choice" in str(serializer.errors[invalid_field][0])

    @pytest.mark.parametrize(
        "input_data, expected_output",
        [
            # Multiple brightness entries.
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
            # Single brightness entry.
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
            # Empty input should return None.
            ({}, {"brightnesses": None}),
            # Non-sequential indices.
            (
                {
                    "brightnessValueInput1": "21",
                    "brightnessBandSelect1": Band.SLOAN_G.value,
                    "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                    "brightnessValueInput3": "22",
                    "brightnessBandSelect3": Band.SLOAN_R.value,
                    "brightnessUnitsSelect3": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
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
    def test_to_internal_value_valid(self, input_data, expected_output):
        """Test valid flat form data for BrightnessesSerializer."""
        serializer = BrightnessesSerializer()
        result = serializer.to_internal_value(input_data)
        assert result == expected_output

    @pytest.mark.parametrize(
        "input_data, expected_message",
        [
            # Missing value.
            (
                {
                    "brightnessBandSelect1": Band.SLOAN_G.value,
                    "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                },
                "A Brightness value is not a valid number.",
            ),
            # Missing band.
            (
                {
                    "brightnessValueInput1": "10.5",
                    "brightnessUnitsSelect1": BrightnessIntegratedUnits.JANSKY.value,
                },
                "A Brightness is missing a band or units.",
            ),
            # Missing units.
            (
                {
                    "brightnessValueInput1": "10.5",
                    "brightnessBandSelect1": Band.SLOAN_G.value,
                },
                "A Brightness is missing a band or units.",
            ),
            # Invalid numeric value.
            (
                {
                    "brightnessValueInput1": "bad",
                    "brightnessBandSelect1": Band.SLOAN_G.value,
                    "brightnessUnitsSelect1": BrightnessIntegratedUnits.AB_MAGNITUDE.value,
                },
                "A Brightness value is not a valid number.",
            ),
        ],
    )
    def test_to_internal_value_invalid(self, input_data, expected_message):
        """Test invalid flat form data."""
        serializer = BrightnessesSerializer()
        with pytest.raises(ValidationError, match=expected_message):
            serializer.to_internal_value(input_data)

    def test_format_gpp_with_validated_data(self):
        """Test that format_gpp returns brightnesses correctly."""
        serializer = BrightnessesSerializer()
        serializer._validated_data = {
            "brightnesses": [
                {
                    "band": Band.SLOAN_R.value,
                    "value": 22.0,
                    "units": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
                }
            ]
        }
        result = serializer.format_gpp()
        assert result == {
            "brightnesses": [
                {
                    "band": Band.SLOAN_R.value,
                    "value": 22.0,
                    "units": BrightnessIntegratedUnits.VEGA_MAGNITUDE.value,
                }
            ]
        }

    def test_format_gpp_returns_none_if_empty(self):
        """Test that format_gpp returns None when brightnesses are empty or missing."""
        serializer = BrightnessesSerializer()
        serializer._validated_data = {"brightnesses": None}
        assert serializer.format_gpp() is None
