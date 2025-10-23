import pytest
from gpp_client.api.enums import ObservingModeType
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.instruments import (
    GMOSNorthLongSlitSerializer,
    GMOSSouthLongSlitSerializer,
    InstrumentRegistry,
)


@pytest.mark.parametrize(
    "input_key, expected_serializer",
    [
        # Valid keys using Enum.
        (ObservingModeType.GMOS_NORTH_LONG_SLIT, GMOSNorthLongSlitSerializer),
        (ObservingModeType.GMOS_SOUTH_LONG_SLIT, GMOSSouthLongSlitSerializer),
        # Valid keys using raw strings.
        ("GMOS_NORTH_LONG_SLIT", GMOSNorthLongSlitSerializer),
        ("GMOS_SOUTH_LONG_SLIT", GMOSSouthLongSlitSerializer),
    ],
)
def test_gpp_instrument_registry_valid(input_key, expected_serializer):
    """Ensure correct serializer is returned for valid keys."""
    assert InstrumentRegistry.get_serializer(input_key) is expected_serializer


@pytest.mark.parametrize(
    "invalid_key",
    [
        "GMOS_EAST_LONG_SLIT",  # Invalid string.
        "FLAMINGOS_2_IFU",  # Not yet registered.
        ObservingModeType.GMOS_SOUTH_IMAGING,  # Valid enum but unregistered.
        "gmos_north_long_slit",  # Incorrect casing.
        "",  # Empty string.
        None,  # None type.
        42,  # Non-string type.
    ],
)
def test_gpp_instrument_registry_invalid(invalid_key):
    """Ensure ValidationError is raised for unsupported instrument types."""
    with pytest.raises(ValidationError) as excinfo:
        InstrumentRegistry.get_serializer(invalid_key)
    assert "Unsupported instrument type" in str(excinfo.value)
