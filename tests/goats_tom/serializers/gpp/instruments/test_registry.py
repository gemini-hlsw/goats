import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.instruments import (
    GPPInstrumentRegistry,
    GPPGMOSNorthLongSlitSerializer,
    GPPGMOSSouthLongSlitSerializer,
)
from gpp_client.api.enums import ObservingModeType
from gpp_client.api.input_types import (
    GmosNorthLongSlitInput,
    GmosSouthLongSlitInput,
)


@pytest.mark.parametrize(
    "input_key, expected_serializer, expected_input_model",
    [
        # Valid keys using Enum.
        (
            ObservingModeType.GMOS_NORTH_LONG_SLIT,
            GPPGMOSNorthLongSlitSerializer,
            GmosNorthLongSlitInput,
        ),
        (
            ObservingModeType.GMOS_SOUTH_LONG_SLIT,
            GPPGMOSSouthLongSlitSerializer,
            GmosSouthLongSlitInput,
        ),
        # Valid keys using raw strings.
        (
            "GMOS_NORTH_LONG_SLIT",
            GPPGMOSNorthLongSlitSerializer,
            GmosNorthLongSlitInput,
        ),
        (
            "GMOS_SOUTH_LONG_SLIT",
            GPPGMOSSouthLongSlitSerializer,
            GmosSouthLongSlitInput,
        ),
    ],
)
def test_gpp_instrument_registry_valid(input_key, expected_serializer, expected_input_model):
    """Ensure correct serializer and input model are returned for valid keys."""
    assert GPPInstrumentRegistry.get_serializer(input_key) is expected_serializer
    assert GPPInstrumentRegistry.get_input_model(input_key) is expected_input_model


@pytest.mark.parametrize(
    "invalid_key",
    [
        "GMOS_EAST_LONG_SLIT",                 # Invalid string.
        "FLAMINGOS_2_IFU",                     # Not yet registered.
        ObservingModeType.GMOS_SOUTH_IMAGING,  # Valid enum but unregistered.
        "gmos_north_long_slit",                # Incorrect casing.
        "",                                    # Empty string.
        None,                                  # None type.
        42,                                    # Non-string type.
    ],
)
def test_gpp_instrument_registry_invalid(invalid_key):
    """Ensure ValidationError is raised for unsupported instrument types."""
    with pytest.raises(ValidationError) as excinfo:
        GPPInstrumentRegistry.get_serializer(invalid_key)
    assert "Unsupported instrument type" in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo:
        GPPInstrumentRegistry.get_input_model(invalid_key)
    assert "Unsupported instrument type" in str(excinfo.value)
