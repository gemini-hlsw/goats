import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import CloneTargetSerializer


@pytest.mark.parametrize(
    "input_data, expected_target_id",
    [
        # Valid target ID.
        ({"hiddenTargetIdInput": "TGT-123"}, "TGT-123"),
    ],
)
def test_valid_clone_target_input(input_data, expected_target_id):
    """Test CloneTargetSerializer with a valid hiddenTargetIdInput."""
    serializer = CloneTargetSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == input_data
    assert serializer.target_id == expected_target_id


@pytest.mark.parametrize(
    "input_data",
    [
        {},  # Missing field.
        {"hiddenTargetIdInput": None},
        {"hiddenTargetIdInput": ""},
    ],
)
def test_invalid_clone_target_input(input_data):
    """Test invalid CloneTargetSerializer cases (missing or blank input)."""
    serializer = CloneTargetSerializer(data=input_data)
    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    assert "hiddenTargetIdInput" in excinfo.value.detail
