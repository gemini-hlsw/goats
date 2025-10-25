import pytest

from goats_tom.serializers.gpp.source_profile.seds.black_body import BlackBodySerializer


@pytest.mark.parametrize(
    "data, expected_validated",
    [
        ({"sedBlackBodyTempK": "600"}, {"sedBlackBodyTempK": 600}),
        ({"sedBlackBodyTempK": 1000}, {"sedBlackBodyTempK": 1000}),
        ({"sedBlackBodyTempK": None}, {"sedBlackBodyTempK": None}),
        ({}, {}),  # Field missing
    ],
)
def test_black_body_serializer_valid_cases(
    data: dict[str, object],
    expected_validated: dict[str, int | None],
) -> None:
    serializer = BlackBodySerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == expected_validated


@pytest.mark.parametrize(
    "data, expected_error",
    [
        ({"sedBlackBodyTempK": 0}, "Ensure this value is greater than or equal to 1."),
        ({"sedBlackBodyTempK": -5}, "Ensure this value is greater than or equal to 1."),
        ({"sedBlackBodyTempK": "3.14"}, "A valid integer is required."),
        ({"sedBlackBodyTempK": "abc"}, "A valid integer is required."),
        ({"sedBlackBodyTempK": "1e3"}, "A valid integer is required."),
    ],
)
def test_black_body_serializer_invalid_cases(
    data: dict[str, object],
    expected_error: str,
) -> None:
    serializer = BlackBodySerializer(data=data)
    assert not serializer.is_valid()
    assert "sedBlackBodyTempK" in serializer.errors
    assert expected_error in serializer.errors["sedBlackBodyTempK"][0]


@pytest.mark.parametrize(
    "data, expected_output",
    [
        ({"sedBlackBodyTempK": "500"}, {"blackBodyTempK": 500}),
        ({"sedBlackBodyTempK": None}, None),
        ({}, None),
    ],
)
def test_black_body_serializer_format_gpp(
    data: dict[str, object],
    expected_output: dict[str, int] | None,
) -> None:
    serializer = BlackBodySerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.format_gpp() == expected_output


def test_black_body_serializer_to_pydantic() -> None:
    """Ensure serializer converts to UnnormalizedSedInput correctly."""
    serializer = BlackBodySerializer(data={"sedBlackBodyTempK": 777})
    assert serializer.is_valid(), serializer.errors
    pydantic_obj = serializer.to_pydantic()
    assert pydantic_obj.black_body_temp_k == 777
