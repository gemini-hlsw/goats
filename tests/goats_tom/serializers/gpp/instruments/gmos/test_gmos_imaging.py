import json

import pytest

from goats_tom.serializers.gpp.instruments import (
    GMOSNorthImagingSerializer,
    GMOSSouthImagingSerializer,
)

SERIALIZERS = [GMOSNorthImagingSerializer, GMOSSouthImagingSerializer]


def variant_payload() -> dict:
    """Build the offset variant the observation form emits."""
    return {
        "variant": "GROUPED",
        "wavelengthOrder": "INCREASING",
        "skyOffsetCount": 1,
        "offsets": "SPIRAL",
        "spiralSize": 12.0,
        "skyOffsets": "NONE",
    }


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_variant_arrives_as_a_json_string(serializer_class) -> None:
    """Test that the variant is parsed from the JSON the form submits."""
    serializer = serializer_class(
        data={"imagingOffsetVariant": json.dumps(variant_payload())}
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {
        "variant": {
            "grouped": {
                "order": "INCREASING",
                "skyCount": 1,
                "offsets": {"spiral": {"size": {"arcseconds": 12.0}}},
            }
        }
    }


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_variant_also_accepts_a_dict(serializer_class) -> None:
    """Test that an already decoded payload is accepted."""
    serializer = serializer_class(data={"imagingOffsetVariant": variant_payload()})
    assert serializer.is_valid(), serializer.errors
    assert serializer.format_gpp() is not None


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_without_a_variant_nothing_is_sent(serializer_class) -> None:
    """Test that an absent variant produces no imaging payload."""
    serializer = serializer_class(data={})
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() is None
    assert serializer.variant is None


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_invalid_json_is_rejected(serializer_class) -> None:
    """Test that a malformed JSON payload raises a validation error."""
    serializer = serializer_class(data={"imagingOffsetVariant": "{not json"})
    assert not serializer.is_valid()
    assert "imagingOffsetVariant" in serializer.errors


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_invalid_variant_is_rejected(serializer_class) -> None:
    """Test that errors from the nested variant serializer surface."""
    serializer = serializer_class(
        data={"imagingOffsetVariant": json.dumps({"variant": "SPIRALLED"})}
    )
    assert not serializer.is_valid()
    assert "variant" in serializer.errors


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_exposure_mode_fields_are_ignored(serializer_class) -> None:
    """Test that stray exposure-mode fields neither block nor reach the payload.

    Imaging keeps its exposure mode inside each filter, so a flat one has nowhere
    to go and must not be forwarded.
    """
    serializer = serializer_class(
        data={
            "imagingOffsetVariant": json.dumps(variant_payload()),
            "exposureModeSelect": "Signal / Noise",
            "snInput": "100",
            "snWavelengthInput": "500",
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert set(serializer.format_gpp()) == {"variant"}


@pytest.mark.parametrize("serializer_class", SERIALIZERS)
def test_to_pydantic_outputs_valid_model(serializer_class) -> None:
    """Test that to_pydantic returns a valid imaging input model."""
    serializer = serializer_class(
        data={"imagingOffsetVariant": json.dumps(variant_payload())}
    )
    assert serializer.is_valid(), serializer.errors

    model = serializer.to_pydantic()
    assert model.model_dump(exclude_none=True) == {
        "variant": {
            "grouped": {
                "order": "INCREASING",
                "sky_count": 1,
                "offsets": {"spiral": {"size": {"arcseconds": 12.0}}},
            }
        }
    }
