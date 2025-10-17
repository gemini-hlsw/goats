import pytest
from rest_framework.serializers import ValidationError
from goats_tom.serializers.gpp.source_profile.seds.black_body import BlackBodySerializer


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (None, None),                   # None input.
        ("", None),                     # Empty string.
        ("300", 300),                   # Valid positive integer.
        ("1000", 1000),                 # Another valid integer.
        ("  500  ", 500),               # Whitespace around valid integer.
    ],
)
def test_validate_sedBlackBodyTempK_valid_cases(input_value, expected_output):
    serializer = BlackBodySerializer()
    assert serializer.validate_sedBlackBodyTempK(input_value) == expected_output


@pytest.mark.parametrize(
    "input_value, expected_exception_message",
    [
        ("-100", "Must be a positive integer (Kelvin)."),  # Negative integer.
        ("abc", "Must be a valid integer."),               # Non-numeric.
        ("0", "Must be a positive integer (Kelvin)."),     # Zero.
        ("3.14", "Must be a valid integer."),              # Float string.
        ("1e3", "Must be a valid integer."),               # Scientific notation.
        ("5.0", "Must be a valid integer."),               # Float with .0
    ],
)
def test_validate_sedBlackBodyTempK_invalid_cases(
    input_value: str, expected_exception_message: str
) -> None:
    serializer = BlackBodySerializer()
    with pytest.raises(ValidationError) as excinfo:
        serializer.validate_sedBlackBodyTempK(input_value)
    assert str(excinfo.value.detail[0]) == expected_exception_message


def test_black_body_serializer_structured_output() -> None:
    """Test full validation and formatting pipeline."""
    data = {"sedBlackBodyTempK": "600"}
    serializer = BlackBodySerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"blackBodyTempK": 600}


def test_black_body_serializer_blank_value() -> None:
    """Test that a blank string results in None in structured output."""
    data = {"sedBlackBodyTempK": ""}
    serializer = BlackBodySerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"blackBodyTempK": None}
