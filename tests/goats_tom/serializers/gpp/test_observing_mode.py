from unittest.mock import MagicMock, patch

import pytest
from gpp_client.api.enums import ObservingModeType
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.observing_mode import ObservingModeSerializer


@pytest.mark.parametrize(
    "instrument_mode, instrument_result",
    [
        (
            ObservingModeType.GMOS_SOUTH_LONG_SLIT.value,
            {
                "centralWavelength": {"nanometers": 750.5},
                "explicitWavelengthDithers": [{"nanometers": 0.0}, {"nanometers": 8.0}],
                "explicitOffsets": [{"arcseconds": 10.0}, {"arcseconds": -10.0}],
            },
        ),
        (
            ObservingModeType.GMOS_NORTH_LONG_SLIT.value,
            {
                "centralWavelength": {"nanometers": 650.0},
                "explicitWavelengthDithers": [{"nanometers": 1.0}],
                "explicitOffsets": [{"arcseconds": 5.0}],
            },
        ),
    ],
)
def test_valid_observing_modes(instrument_mode, instrument_result):
    mock_serializer = MagicMock()
    mock_serializer.is_valid.return_value = True
    mock_serializer.format_gpp.return_value = instrument_result

    with patch(
        "goats_tom.serializers.gpp.observing_mode.InstrumentRegistry.get_serializer",
        return_value=lambda data: mock_serializer,
    ):
        input_data = {"hiddenObservingModeInput": instrument_mode}
        serializer = ObservingModeSerializer(data=input_data)
        assert serializer.is_valid()
        assert serializer.format_gpp() == {instrument_mode.lower(): instrument_result}


@pytest.mark.parametrize(
    "input_data, expected_error",
    [
        (
            {"hiddenObservingModeInput": "INVALID_MODE"},
            "is not a valid choice",
        ),
        (
            {},
            "This field is required",
        ),
    ],
)
def test_invalid_mode_selection(input_data, expected_error):
    serializer = ObservingModeSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)
    assert expected_error in str(excinfo.value)


def test_format_gpp_returns_none_when_instrument_has_no_data():
    mock_serializer = MagicMock()
    mock_serializer.is_valid.return_value = True
    mock_serializer.format_gpp.return_value = None

    with patch(
        "goats_tom.serializers.gpp.observing_mode.InstrumentRegistry.get_serializer",
        return_value=lambda data: mock_serializer,
    ):
        input_data = {
            "hiddenObservingModeInput": ObservingModeType.GMOS_SOUTH_LONG_SLIT.value
        }
        serializer = ObservingModeSerializer(data=input_data)
        assert serializer.is_valid()
        assert serializer.format_gpp() is None


def test_to_pydantic_model_returns_instance():
    # Return the properly nested dictionary as expected by ObservingModeInput
    mock_serializer = MagicMock()
    mock_serializer.is_valid.return_value = True
    mock_serializer.format_gpp.return_value = {
        "centralWavelength": {"nanometers": 750.5}
    }

    with patch(
        "goats_tom.serializers.gpp.observing_mode.InstrumentRegistry.get_serializer",
        return_value=lambda data: mock_serializer,
    ):
        input_data = {
            "hiddenObservingModeInput": ObservingModeType.GMOS_SOUTH_LONG_SLIT.value
        }
        serializer = ObservingModeSerializer(data=input_data)
        assert serializer.is_valid()

        model = serializer.to_pydantic()
        from gpp_client.api.input_types import ObservingModeInput

        assert isinstance(model, ObservingModeInput)
        assert model.gmos_south_long_slit is not None
        assert model.gmos_south_long_slit.central_wavelength.nanometers == 750.5
