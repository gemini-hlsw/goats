import pytest
from gpp_client.api.input_types import SourceProfileInput
from rest_framework.exceptions import ErrorDetail, ValidationError

from goats_tom.serializers.gpp.source_profile.seds.registry import SEDRegistry, SEDType
from goats_tom.serializers.gpp.source_profile.source_profile import (
    SourceProfileSerializer,
    SourceProfileType,
)


@pytest.mark.django_db
class TestSourceProfileSerializer:
    """Tests for SourceProfileSerializer."""

    @pytest.fixture
    def base_valid_data(self) -> dict:
        return {
            "sedProfileTypeSelect": SourceProfileType.POINT.value,
            "sedTypeSelect": SEDType.BLACK_BODY.value,
        }

    @pytest.fixture
    def mock_brightness(self, mocker):
        """Mock the BrightnessesSerializer."""
        mock_cls = mocker.patch(
            "goats_tom.serializers.gpp.source_profile.source_profile.BrightnessesSerializer"
        )
        instance = mocker.MagicMock()
        instance.is_valid.return_value = True
        instance.format_gpp.return_value = {
            "brightnesses": [{"band": "SLOAN_R", "value": 22.0}]
        }
        mock_cls.return_value = instance
        return instance

    @pytest.fixture
    def mock_sed(self, mocker):
        """Mock the SEDRegistry.get_serializer()."""
        mock_cls = mocker.MagicMock()
        instance = mocker.MagicMock()
        instance.is_valid.return_value = True
        instance.format_gpp.return_value = {"mocked": "data"}
        mock_cls.return_value = instance
        mocker.patch.object(SEDRegistry, "get_serializer", return_value=mock_cls)
        return instance

    def test_valid_with_sed(self, base_valid_data, mock_brightness, mock_sed):
        """Test valid input with SED and brightness data."""
        serializer = SourceProfileSerializer(data=base_valid_data)
        assert serializer.is_valid(), serializer.errors

        formatted = serializer.format_gpp()
        assert formatted == {
            "point": {
                "bandNormalized": {
                    "sed": {"mocked": "data"},
                    "brightnesses": [{"band": "SLOAN_R", "value": 22.0}],
                }
            }
        }

    def test_to_pydantic_returns_valid_model(
        self, base_valid_data, mock_brightness, mock_sed
    ):
        """Test that `to_pydantic()` returns a valid SourceProfileInput model."""
        serializer = SourceProfileSerializer(data=base_valid_data)
        assert serializer.is_valid(), serializer.errors
        model = serializer.to_pydantic()
        assert isinstance(model, SourceProfileInput)
        assert model.point is not None
        assert model.point.band_normalized is not None

    @pytest.mark.parametrize("sed_type", [None])
    def test_valid_without_sed(self, mocker, sed_type, mock_brightness):
        """Test valid input without SED type (field omitted or None)."""
        mock_registry = mocker.patch.object(SEDRegistry, "get_serializer")

        data = {
            "sedProfileTypeSelect": SourceProfileType.POINT.value,
        }
        if sed_type is not None:
            data["sedTypeSelect"] = sed_type

        serializer = SourceProfileSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        result = serializer.format_gpp()
        assert "point" in result
        assert "bandNormalized" in result["point"]
        assert "brightnesses" in result["point"]["bandNormalized"]
        assert "sed" not in result["point"]["bandNormalized"]
        mock_registry.assert_not_called()

    def test_format_gpp_returns_none_when_profile_type_missing(
        self, mock_brightness, mocker
    ):
        """Test `format_gpp()` returns None if sedProfileTypeSelect is not provided."""
        data = {}  # Completely missing profile type and sed
        serializer = SourceProfileSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.format_gpp() is None

    def test_invalid_sed_profile_type(self):
        """Test invalid sedProfileTypeSelect is rejected."""
        data = {"sedProfileTypeSelect": "invalid_type"}
        serializer = SourceProfileSerializer(data=data)
        assert not serializer.is_valid()
        assert "sedProfileTypeSelect" in serializer.errors

    @pytest.mark.parametrize(
        "data, expected_field",
        [
            (
                {
                    "sedProfileTypeSelect": SourceProfileType.POINT.value,
                    "sedTypeSelect": "invalid",
                },
                "sedTypeSelect",
            ),
        ],
    )
    def test_invalid_fields(self, data: dict, expected_field: str) -> None:
        """Test invalid enum values."""
        serializer = SourceProfileSerializer(data=data)
        assert not serializer.is_valid()
        assert expected_field in serializer.errors

    def test_nested_sed_validation_error(self, mocker, mock_brightness):
        """Test that nested SED serializer raising ValidationError propagates correctly."""
        data = {
            "sedProfileTypeSelect": SourceProfileType.POINT.value,
            "sedTypeSelect": SEDType.BLACK_BODY.value,
        }

        mock_cls = mocker.MagicMock()
        instance = mocker.MagicMock()
        instance.is_valid.side_effect = ValidationError(
            {"non_field_errors": [ErrorDetail("Invalid SED data.", code="invalid")]}
        )
        mock_cls.return_value = instance
        mocker.patch.object(SEDRegistry, "get_serializer", return_value=mock_cls)

        serializer = SourceProfileSerializer(data=data)
        with pytest.raises(ValidationError, match="Invalid SED data"):
            serializer.is_valid(raise_exception=True)

    def test_format_gpp_returns_none_when_empty(self, mocker, mock_brightness):
        """Test `format_gpp()` returns None if no brightness or SED data are present."""
        mock_brightness.format_gpp.return_value = None
        data = {"sedProfileTypeSelect": SourceProfileType.POINT.value}
        serializer = SourceProfileSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.format_gpp() is None
