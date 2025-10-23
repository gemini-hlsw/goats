from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from rest_framework import serializers

from goats_tom.serializers.gpp._base_gpp import _BaseGPPSerializer


class DummyModel(BaseModel):
    foo: str
    bar: int


class ValidSerializer(_BaseGPPSerializer):
    pydantic_model = DummyModel

    foo = serializers.CharField()
    bar = serializers.IntegerField()

    def format_gpp(self) -> dict[str, Any]:
        return {
            "foo": self.validated_data["foo"],
            "bar": self.validated_data["bar"],
        }


class NoneReturningSerializer(ValidSerializer):
    def format_gpp(self) -> None:
        return None


class InvalidDataSerializer(ValidSerializer):
    def format_gpp(self) -> dict[str, Any]:
        return {
            "foo": 123,  # Wrong type
            "bar": "not-an-int",  # Wrong type
        }


@pytest.mark.parametrize(
    "serializer_class, input_data, expected_gpp",
    [
        (ValidSerializer, {"foo": "a", "bar": 1}, {"foo": "a", "bar": 1}),
        (NoneReturningSerializer, {"foo": "b", "bar": 2}, None),
    ],
)
def test_to_gpp_behavior(serializer_class, input_data, expected_gpp):
    """Test to_gpp returns expected data or None based on format_gpp()."""
    serializer = serializer_class(data=input_data)
    assert serializer.is_valid()
    result = serializer.to_gpp()
    assert result == expected_gpp


@pytest.mark.parametrize(
    "serializer_class, input_data, expected_model_type",
    [
        (ValidSerializer, {"foo": "hello", "bar": 42}, DummyModel),
        (NoneReturningSerializer, {"foo": "hello", "bar": 42}, type(None)),
    ],
)
def test_to_pydantic_valid_cases(serializer_class, input_data, expected_model_type):
    """Test to_pydantic returns expected model or None depending on formatted output."""
    serializer = serializer_class(data=input_data)
    assert serializer.is_valid()
    result = serializer.to_pydantic()
    assert isinstance(result, expected_model_type)


def test_to_pydantic_invalid_schema_raises_validation_error():
    """Test to_pydantic raises ValidationError for invalid formatted schema."""
    serializer = InvalidDataSerializer(data={"foo": "bad", "bar": 999})
    assert serializer.is_valid()
    with pytest.raises(ValidationError):
        serializer.to_pydantic()


def test_to_pydantic_missing_pydantic_model_raises():
    """Test to_pydantic raises ValueError if pydantic_model is not set."""

    class NoModelSerializer(ValidSerializer):
        pydantic_model = None

    serializer = NoModelSerializer(data={"foo": "x", "bar": 5})
    assert serializer.is_valid()
    with pytest.raises(ValueError):
        serializer.to_pydantic()


@pytest.mark.parametrize("method_name", ["to_gpp", "to_pydantic"])
def test_methods_raise_if_called_before_is_valid(method_name):
    """Test DRF raises AssertionError if to_gpp or to_pydantic is called before .is_valid()."""
    serializer = ValidSerializer()
    method = getattr(serializer, method_name)
    with pytest.raises(AssertionError):
        method()


def test_format_gpp_not_implemented():
    """Test that base class raises NotImplementedError if format_gpp() is not overridden."""

    class Incomplete(_BaseGPPSerializer):
        def __init__(self):
            super().__init__()
            self._validated_data = {}

        @property
        def validated_data(self):
            return self._validated_data

    serializer = Incomplete()
    with pytest.raises(NotImplementedError):
        serializer.format_gpp()


def test_finalize_gpp_can_wrap_result():
    """Test that finalize_gpp can be overridden to augment the formatted dict."""

    class WrappedSerializer(ValidSerializer):
        def finalize_gpp(
            self, formatted: dict[str, Any] | None
        ) -> dict[str, Any] | None:
            if formatted:
                formatted["extra"] = True
            return formatted

    serializer = WrappedSerializer(data={"foo": "test", "bar": 3})
    assert serializer.is_valid()
    result = serializer.to_gpp()
    assert result["foo"] == "test"
    assert result["bar"] == 3
    assert result["extra"] is True


def test_finalize_pydantic_can_wrap_model():
    """Test that finalize_pydantic can override and modify the returned model."""

    class WrappedSerializer(ValidSerializer):
        def finalize_pydantic(self, model: BaseModel) -> BaseModel:
            return model.model_copy(update={"foo": model.foo.upper()})

    serializer = WrappedSerializer(data={"foo": "wrap", "bar": 9})
    assert serializer.is_valid()
    model = serializer.to_pydantic()
    assert model.foo == "WRAP"
    assert model.bar == 9
