import pytest
from rest_framework import serializers

from goats_tom.serializers.gpp._base import _BaseSerializer


class DummySerializer(_BaseSerializer):
    text = serializers.CharField(allow_null=True, required=False)
    number = serializers.IntegerField(allow_null=True, required=False)
    decimal = serializers.FloatField(allow_null=True, required=False)
    flag = serializers.BooleanField(allow_null=True, required=False)


@pytest.mark.parametrize(
    "input_data, expected",
    [
        # Blank string in CharField.
        ({"text": "", "number": "1", "decimal": "1.1", "flag": "true"},
         {"text": None, "number": 1, "decimal": 1.1, "flag": True}),

        # Whitespace in CharField.
        ({"text": "   ", "number": "2", "decimal": "2.2", "flag": "false"},
         {"text": None, "number": 2, "decimal": 2.2, "flag": False}),

        # None explicitly.
        ({"text": None, "number": "3", "decimal": "3.3", "flag": "True"},
         {"text": None, "number": 3, "decimal": 3.3, "flag": True}),

        # Valid normal values.
        ({"text": "hello", "number": "4", "decimal": "4.4", "flag": "False"},
         {"text": "hello", "number": 4, "decimal": 4.4, "flag": False}),
    ],
)
def test_base_serializer_normalizes_and_casts_form_data(
    input_data: dict[str, str | None],
    expected: dict[str, str | int | float | bool | None],
) -> None:
    serializer = DummySerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == expected
