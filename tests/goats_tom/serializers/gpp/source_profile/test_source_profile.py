import pytest
from unittest.mock import patch, MagicMock
from rest_framework.serializers import ValidationError

from goats_tom.serializers.gpp.source_profile.seds.registry import SEDRegistry, SEDType
from goats_tom.serializers.gpp.source_profile.source_profile import (
    SourceProfileSerializer,
    SourceProfileType,
)


@pytest.mark.parametrize(
    "data, expected_result",
    [
        (
            # Case: Valid profile and valid SED type.
            {
                "sedProfileTypeSelect": SourceProfileType.POINT.value,
                "sedTypeSelect": SEDType.BLACK_BODY.value,
            },
            {
                SourceProfileType.POINT.value: {
                    "bandNormalized": {"sed": {"mocked": "data"}}
                }
            },
        ),
        (
            # Case: Valid profile with no SED type (empty string).
            {
                "sedProfileTypeSelect": SourceProfileType.POINT.value,
                "sedTypeSelect": "",
            },
            {
                SourceProfileType.POINT.value: {
                    "bandNormalized": {"sed": None}
                }
            },
        ),
        (
            # Case: Valid profile with missing SED type.
            {
                "sedProfileTypeSelect": SourceProfileType.POINT.value,
            },
            {
                SourceProfileType.POINT.value: {
                    "bandNormalized": {"sed": None}
                }
            },
        ),
    ],
)
def test_source_profile_serializer_valid(data, expected_result):
    """Test valid cases for SourceProfileSerializer."""
    with patch.object(SEDRegistry, "get_serializer") as mock_get_serializer:
        # Create a mock instance to simulate the nested serializer.
        mock_instance = MagicMock()
        mock_instance.is_valid.return_value = True
        mock_instance.validated_data = {"mocked": "data"}

        # Make get_serializer() return a mock class that returns our instance.
        mock_get_serializer.return_value = MagicMock(return_value=mock_instance)

        serializer = SourceProfileSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == expected_result

        if "sedTypeSelect" in data and data["sedTypeSelect"]:
            mock_get_serializer.assert_called_once_with(data["sedTypeSelect"])
            mock_instance.is_valid.assert_called_once()
        else:
            mock_get_serializer.assert_not_called()


@pytest.mark.parametrize(
    "data, expected_error_field",
    [
        (
            # Blank profile type (not allowed).
            {
                "sedProfileTypeSelect": "",
                "sedTypeSelect": "",
            },
            "sedProfileTypeSelect",
        ),
        (
            # Invalid SED type (not in enum).
            {
                "sedProfileTypeSelect": SourceProfileType.POINT.value,
                "sedTypeSelect": "invalid_sed_type",
            },
            "sedTypeSelect",
        ),
        (
            # Missing profile type entirely.
            {
                "sedTypeSelect": SEDType.BLACK_BODY.value,
            },
            "sedProfileTypeSelect",
        ),
    ],
)
def test_source_profile_serializer_invalid(data, expected_error_field):
    """Test invalid input scenarios for SourceProfileSerializer."""
    serializer = SourceProfileSerializer(data=data)
    is_valid = serializer.is_valid()
    assert not is_valid
    assert expected_error_field in serializer.errors


def test_source_profile_serializer_nested_validation_error():
    """Test when nested SED serializer raises its own validation error."""
    data = {
        "sedProfileTypeSelect": SourceProfileType.POINT.value,
        "sedTypeSelect": SEDType.BLACK_BODY.value,
    }

    with patch.object(SEDRegistry, "get_serializer") as mock_get_serializer:
        mock_instance = MagicMock()
        mock_instance.is_valid.side_effect = ValidationError("Invalid SED data.")

        mock_get_serializer.return_value = MagicMock(return_value=mock_instance)

        serializer = SourceProfileSerializer(data=data)

        with pytest.raises(ValidationError, match="Invalid SED data."):
            serializer.is_valid(raise_exception=True)
