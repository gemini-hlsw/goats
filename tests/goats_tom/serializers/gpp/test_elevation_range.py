import pytest
from rest_framework.exceptions import ValidationError
from goats_tom.serializers.gpp.elevation_range import ElevationRangeSerializer


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Valid Air Mass Mode inputs.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "1.0",
                "airMassMaximumInput": "2.0",
            },
            {"airMass": {"min": 1.0, "max": 2.0}},
        ),
        # Air Mass mode with only min.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "1.2",
                "airMassMaximumInput": "",
            },
            {"airMass": {"min": 1.2, "max": None}},
        ),
        # Air Mass mode with only max.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "",
                "airMassMaximumInput": "2.5",
            },
            {"airMass": {"min": None, "max": 2.5}},
        ),
        # Valid Hour Angle Mode inputs.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": "-2.5",
                "haMaximumInput": "3.0",
            },
            {"hourAngle": {"minHours": -2.5, "maxHours": 3.0}},
        ),
        # Hour Angle with only minHours.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": "-1.5",
                "haMaximumInput": "",
            },
            {"hourAngle": {"minHours": -1.5, "maxHours": None}},
        ),
        # Hour Angle with only maxHours.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": "",
                "haMaximumInput": "2.5",
            },
            {"hourAngle": {"minHours": None, "maxHours": 2.5}},
        ),
        # Provide values for both hour angle and air mass; should prioritize air mass.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "1.0",
                "airMassMaximumInput": "2.0",
                "haMinimumInput": "-2.5",
                "haMaximumInput": "3.0",
            },
            {"airMass": {"min": 1.0, "max": 2.0}},
        ),
    ],
)
def test_validate_valid_inputs(input_data, expected_output):
    """Test valid elevation range inputs."""
    serializer = ElevationRangeSerializer()
    result = serializer.validate(input_data)
    assert result == expected_output


@pytest.mark.parametrize(
    "input_data, expected_exception_message",
    [
        # Air Mass Mode invalid cases.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "",
                "airMassMaximumInput": "",
            },
            "Air mass range must have at least one value.",
        ),
        # Air Mass non-numeric.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": "abc",
                "airMassMaximumInput": "2.0",
            },
            "Air mass values must be numeric.",
        ),
        # Hour Angle Mode invalid cases.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": "",
                "haMaximumInput": "",
            },
            "Hour angle range must have at least one value.",
        ),
        # Hour Angle non-numeric.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": "1.5",
                "haMaximumInput": "xyz",
            },
            "Hour angle values must be numeric.",
        ),
        # Invalid mode.
        (
            {
                "elevationRangeSelect": "Invalid Mode",
            },
            "Invalid elevation range mode selected.",
        ),
    ],
)
def test_validate_invalid_inputs(input_data, expected_exception_message):
    """Test invalid elevation range inputs."""
    serializer = ElevationRangeSerializer()
    with pytest.raises(ValidationError) as excinfo:
        serializer.validate(input_data)
    assert expected_exception_message in str(excinfo.value.detail[0])
