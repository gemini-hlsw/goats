import pytest

from goats_tom.serializers.gpp.instruments import GMOSNorthLongSlitSerializer

@pytest.fixture(autouse=True)
def mock_exposure_mode_serializer(mocker):
    """
    Automatically mock ExposureModeSerializer inside GMOS serializers so GMOS tests
    do not need to include exposure-mode fields.
    """
    mocker.patch(
        "goats_tom.serializers.gpp.instruments.gmos._base_gmos.ExposureModeSerializer.is_valid",
        return_value=True,
    )

    mocker.patch(
        "goats_tom.serializers.gpp.instruments.gmos._base_gmos.ExposureModeSerializer.format_gpp",
        return_value=None,
    )

@pytest.mark.parametrize(
    "input_data",
    [
        {
            "centralWavelengthInput": "750.5",
            "wavelengthDithersInput": "0.0, 8.0, -8.0",
            "spatialOffsetsInput": "0.0, 15.0, -15.0",
        },
        {"centralWavelengthInput": "700.0"},
        {"wavelengthDithersInput": "1.0, 2.0"},
        {"spatialOffsetsInput": "5.5, -5.5"},
        {
            "wavelengthDithersInput": " 1.0 , , 2.0 ",
            "spatialOffsetsInput": " , 10.0 , -10.0",
        },
    ],
)
def test_gmos_north_longslit_valid_inputs(input_data: dict[str, str], mocker) -> None:
    """Test that valid inputs are accepted."""
    serializer = GMOSNorthLongSlitSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize(
    "input_data, expected_field, expected_error",
    [
        (
            {"centralWavelengthInput": "not_a_number"},
            "centralWavelengthInput",
            "A valid number is required.",
        ),
        (
            {"wavelengthDithersInput": "1.0, not_a_number"},
            "wavelengthDithersInput",
            "Invalid float value",
        ),
        (
            {"spatialOffsetsInput": "0.0, fail"},
            "spatialOffsetsInput",
            "Invalid float value",
        ),
    ],
)
def test_gmos_north_longslit_invalid_inputs(
    input_data: dict[str, str], expected_field: str, expected_error: str, mocker
) -> None:
    """Test that invalid inputs raise expected validation errors."""
    serializer = GMOSNorthLongSlitSerializer(data=input_data)
    assert not serializer.is_valid()
    assert expected_field in serializer.errors
    assert expected_error in str(serializer.errors[expected_field][0])


def test_format_gpp_outputs_structured_data(mocker) -> None:
    """Test that format_gpp returns correctly structured GPP-compatible output."""
    input_data = {
        "centralWavelengthInput": "750.5",
        "wavelengthDithersInput": "0.0, 8.0, -8.0",
        "spatialOffsetsInput": "0.0, 15.0, -15.0",
    }
    serializer = GMOSNorthLongSlitSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors

    expected = {
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
    assert serializer.format_gpp() == expected


def test_to_pydantic_outputs_valid_model(mocker) -> None:
    """Test that to_pydantic returns a valid Pydantic model."""
    input_data = {
        "centralWavelengthInput": "750.5",
        "wavelengthDithersInput": "1.0, -1.0",
        "spatialOffsetsInput": "5.0, -5.0",
    }
    serializer = GMOSNorthLongSlitSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    model = serializer.to_pydantic()
    assert model.model_dump(exclude_none=True) == {
        "central_wavelength": {"nanometers": 750.5},
        "explicit_wavelength_dithers": [{"nanometers": 1.0}, {"nanometers": -1.0}],
        "explicit_offsets": [{"arcseconds": 5.0}, {"arcseconds": -5.0}],
    }
