from unittest.mock import patch

import pytest
from gpp_client.api.enums import (
    CloudExtinctionPreset,
    ImageQualityPreset,
    SkyBackground,
    WaterVapor,
)
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.observation import ObservationSerializer


@pytest.fixture
def minimal_input():
    return {
        "observerNotesTextarea": "Test note",
        "hiddenObservingModeInput": "GMOS_SOUTH_LONG_SLIT",
        "centralWavelengthInput": "750",
        "spatialOffsetsInput": "0.0, 1.0",
        "wavelengthDithersInput": "0.0, 1.0",
        "posAngleConstraintModeSelect": "FIXED",
        "posAngleConstraintAngleInput": 180.0,
        "exposureModeSelect": "Signal / Noise",
        "snInput": 100.0,
        "snWavelengthInput": 750.0,
        "imageQualitySelect": ImageQualityPreset.ONE_POINT_ZERO.value,
        "cloudExtinctionSelect": CloudExtinctionPreset.ONE_POINT_ZERO.value,
        "skyBackgroundSelect": SkyBackground.DARK.value,
        "waterVaporSelect": WaterVapor.MEDIAN.value,
        "elevationRangeSelect": "Air Mass",
        "airMassMinimumInput": 1.0,
        "airMassMaximumInput": 2.0,
    }


@pytest.fixture
def patched_subserializers():
    with (
        patch(
            "goats_tom.serializers.gpp.observation.ObservingModeSerializer"
        ) as MockOM,
        patch(
            "goats_tom.serializers.gpp.observation.ConstraintSetSerializer"
        ) as MockCS,
        patch("goats_tom.serializers.gpp.observation.PosAngleSerializer") as MockPA,
        patch("goats_tom.serializers.gpp.observation.ExposureModeSerializer") as MockEM,
    ):
        om = MockOM.return_value
        om.is_valid.return_value = True
        om.format_gpp.return_value = {
            "gmos_south_long_slit": {"centralWavelength": {"nanometers": 750.0}}
        }

        cs = MockCS.return_value
        cs.is_valid.return_value = True
        cs.format_gpp.return_value = {"imageQuality": "IQ_70"}

        pa = MockPA.return_value
        pa.is_valid.return_value = True
        pa.format_gpp.return_value = {"mode": "FIXED", "angle": {"degrees": 180.0}}

        em = MockEM.return_value
        em.is_valid.return_value = True
        em.format_gpp.return_value = {
            "signalToNoise": {"value": 100.0, "wavelength": {"nanometers": 750.0}}
        }

        yield


def test_valid_observation_format_gpp(minimal_input, patched_subserializers):
    """Test full format_gpp output with valid nested serializers."""
    serializer = ObservationSerializer(data=minimal_input)
    assert serializer.is_valid()
    formatted = serializer.format_gpp()
    assert formatted["observerNotes"] == "Test note"
    assert "observingMode" in formatted
    assert "constraintSet" in formatted
    assert "posAngleConstraint" in formatted
    assert (
        formatted["scienceRequirements"]["exposureTimeMode"]["signalToNoise"]["value"]
        == 100.0
    )


@pytest.mark.parametrize(
    "field, value, expected_error",
    [
        ("hiddenObservingModeInput", "INVALID", "is not a valid choice"),
        ("posAngleConstraintModeSelect", None, "This field is required."),
        ("snInput", None, "Both S/N value and wavelength are required"),
    ],
)
def test_invalid_required_fields(field, value, expected_error, minimal_input):
    """Test that required fields raise validation errors when invalid or missing."""
    data = minimal_input.copy()
    if value is None:
        data.pop(field, None)
    else:
        data[field] = value

    serializer = ObservationSerializer(data=data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    assert expected_error in str(excinfo.value)
