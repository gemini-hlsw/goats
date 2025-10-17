import pytest
from rest_framework.exceptions import ValidationError
from goats_tom.serializers.gpp.source_profile.seds.registry import SEDRegistry, SEDType
from goats_tom.serializers.gpp.source_profile.seds import BlackBodySerializer

@pytest.mark.parametrize(
    "key, expected_serializer",
    [
        (SEDType.BLACK_BODY, BlackBodySerializer),  # Valid enum key.
        ("blackBodyTempK", BlackBodySerializer),    # Valid string key.
    ],
)
def test_get_serializer_with_valid_keys(key, expected_serializer):
    serializer_class = SEDRegistry.get_serializer(key)
    assert serializer_class == expected_serializer


@pytest.mark.parametrize(
    "key",
    [
        "invalidKey",          # Invalid string key.
        None,                  # None as key.
        123,                   # Non-string, non-enum key.
        "",                    # Empty string key.
    ],
)
def test_get_serializer_with_invalid_keys(key):
    with pytest.raises(ValidationError, match=f"Unsupported SED type: {key}"):
        SEDRegistry.get_serializer(key)
