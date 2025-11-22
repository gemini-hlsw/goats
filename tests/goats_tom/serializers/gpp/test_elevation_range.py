import pytest
from gpp_client.api.input_types import ElevationRangeInput
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.elevation_range import ElevationRangeSerializer


@pytest.mark.parametrize(
    "input_data",
    [
        # Air Mass mode: both min and max.
        {
            "elevationRangeSelect": "Air Mass",
            "airMassMinimumInput": 1.0,
            "airMassMaximumInput": 2.0,
        },
        # Air Mass mode: only min.
        {
            "elevationRangeSelect": "Air Mass",
            "airMassMinimumInput": 1.2,
            "airMassMaximumInput": None,
        },
        # Air Mass mode: only max.
        {
            "elevationRangeSelect": "Air Mass",
            "airMassMinimumInput": None,
            "airMassMaximumInput": 2.5,
        },
        # Hour Angle mode: both min and max.
        {
            "elevationRangeSelect": "Hour Angle",
            "haMinimumInput": -2.5,
            "haMaximumInput": 3.0,
        },
        # Hour Angle mode: only min.
        {
            "elevationRangeSelect": "Hour Angle",
            "haMinimumInput": -1.5,
            "haMaximumInput": None,
        },
        # Hour Angle mode: only max.
        {
            "elevationRangeSelect": "Hour Angle",
            "haMinimumInput": None,
            "haMaximumInput": 2.5,
        },
    ],
)
def test_valid_elevation_range(input_data: dict) -> None:
    """
    Test that valid elevation range inputs pass serializer validation.
    """
    serializer = ElevationRangeSerializer(data=input_data)
    assert serializer.is_valid(), f"Unexpected validation errors: {serializer.errors}"


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": 1.0,
                "airMassMaximumInput": 2.0,
            },
            {"airMass": {"min": 1.0, "max": 2.0}},
        ),
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": -2.0,
                "haMaximumInput": 2.5,
            },
            {"hourAngle": {"minHours": -2.0, "maxHours": 2.5}},
        ),
    ],
)
def test_format_gpp(input_data: dict, expected_output: dict) -> None:
    """
    Test that `format_gpp()` produces the correct GPP dictionary output.
    """
    serializer = ElevationRangeSerializer(data=input_data)
    assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"
    result = serializer.format_gpp()
    assert result == expected_output, "format_gpp() output mismatch."


@pytest.mark.parametrize(
    "input_data, expected_dict",
    [
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": 1.1,
                "airMassMaximumInput": None,
            },
            {"air_mass": {"min": 1.1}},
        ),
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": None,
                "haMaximumInput": 1.7,
            },
            {"hour_angle": {"max_hours": 1.7}},
        ),
    ],
)
def test_to_pydantic(input_data: dict, expected_dict: dict) -> None:
    """
    Test that `to_pydantic()` returns a valid ElevationRangeInput model.
    """
    serializer = ElevationRangeSerializer(data=input_data)
    assert serializer.is_valid(), f"Unexpected errors: {serializer.errors}"

    model = serializer.to_pydantic()
    assert isinstance(model, ElevationRangeInput)
    assert model.model_dump(exclude_none=True) == expected_dict, (
        "Pydantic model data mismatch."
    )


@pytest.mark.parametrize(
    "input_data, expected_error",
    [
        # Air Mass mode missing both min and max.
        (
            {
                "elevationRangeSelect": "Air Mass",
                "airMassMinimumInput": None,
                "airMassMaximumInput": None,
            },
            "At least one air mass boundary (min or max) must be provided.",
        ),
        # Hour Angle mode missing both min and max.
        (
            {
                "elevationRangeSelect": "Hour Angle",
                "haMinimumInput": None,
                "haMaximumInput": None,
            },
            "At least one hour angle boundary (min or max) must be provided.",
        ),
        # Invalid mode.
        (
            {
                "elevationRangeSelect": "Invalid Mode",
                "airMassMinimumInput": 1.0,
            },
            "is not a valid choice",
        ),
    ],
)
def test_invalid_elevation_range(input_data: dict, expected_error: str) -> None:
    """
    Test that invalid elevation range inputs raise ValidationError with expected message.
    """
    serializer = ElevationRangeSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    assert expected_error in str(excinfo.value), (
        f"Expected error '{expected_error}' not found."
    )
