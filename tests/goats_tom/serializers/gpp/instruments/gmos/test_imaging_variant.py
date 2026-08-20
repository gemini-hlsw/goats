import pytest

from goats_tom.serializers.gpp.instruments import ImagingVariantSerializer


def offset(p: float | None, q: float | None) -> dict:
    """Build the p/q payload the form emits."""
    return {"p": {"arcseconds": p}, "q": {"arcseconds": q}}


def grouped(**overrides) -> dict:
    """Build a grouped variant payload with a spiral generator."""
    data = {
        "variant": "GROUPED",
        "wavelengthOrder": "DECREASING",
        "skyOffsetCount": 2,
        "offsets": "SPIRAL",
        "spiralSize": 10.0,
        "skyOffsets": "NONE",
    }
    data.update(overrides)
    return data


def test_grouped_spiral_formats_for_gpp() -> None:
    """Test that a grouped spiral variant is formatted for GPP."""
    serializer = ImagingVariantSerializer(data=grouped())
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {
        "grouped": {
            "order": "DECREASING",
            "skyCount": 2,
            "offsets": {"spiral": {"size": {"arcseconds": 10.0}}},
        }
    }


def test_none_generator_is_omitted() -> None:
    """Test that a generator set to NONE is left out of the payload."""
    serializer = ImagingVariantSerializer(data=grouped(offsets="NONE", spiralSize=None))
    assert serializer.is_valid(), serializer.errors

    formatted = serializer.format_gpp()
    assert "offsets" not in formatted["grouped"]
    assert "skyOffsets" not in formatted["grouped"]


def test_interleaved_has_no_wavelength_order() -> None:
    """Test that the wavelength order is dropped for an interleaved variant."""
    serializer = ImagingVariantSerializer(
        data=grouped(variant="INTERLEAVED", wavelengthOrder="INCREASING")
    )
    assert serializer.is_valid(), serializer.errors

    assert "order" not in serializer.format_gpp()["interleaved"]


def test_enumerated_offsets_keep_guiding() -> None:
    """Test that enumerated offsets carry their guide state."""
    serializer = ImagingVariantSerializer(
        data=grouped(
            offsets="ENUMERATED",
            spiralSize=None,
            explicitOffsets=[
                {"offset": offset(1.0, 2.0), "guiding": "ENABLED"},
                {"offset": offset(3.0, 4.0), "guiding": "DISABLED"},
            ],
        )
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp()["grouped"]["offsets"] == {
        "enumerated": {
            "values": [
                {"offset": offset(1.0, 2.0), "guiding": "ENABLED"},
                {"offset": offset(3.0, 4.0), "guiding": "DISABLED"},
            ]
        }
    }


def test_uniform_generator_uses_both_corners() -> None:
    """Test that a uniform generator is formatted from its two corners."""
    serializer = ImagingVariantSerializer(
        data=grouped(
            offsets="UNIFORM",
            spiralSize=None,
            uniformCornerAP=-5.0,
            uniformCornerAQ=-5.0,
            uniformCornerBP=5.0,
            uniformCornerBQ=5.0,
        )
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp()["grouped"]["offsets"] == {
        "uniform": {"cornerA": offset(-5.0, -5.0), "cornerB": offset(5.0, 5.0)}
    }


def test_sky_generator_uses_its_own_parameters() -> None:
    """Test that the sky generator reads the sky-prefixed parameters."""
    serializer = ImagingVariantSerializer(
        data=grouped(
            skyOffsets="RANDOM",
            skyRandomSize=8.0,
            skyRandomCenterP=1.0,
            skyRandomCenterQ=2.0,
        )
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp()["grouped"]["skyOffsets"] == {
        "random": {"size": {"arcseconds": 8.0}, "center": offset(1.0, 2.0)}
    }


def test_centre_is_omitted_when_not_given() -> None:
    """Test that a generator without a centre does not send one."""
    serializer = ImagingVariantSerializer(data=grouped())
    assert serializer.is_valid(), serializer.errors

    assert "center" not in serializer.format_gpp()["grouped"]["offsets"]["spiral"]


def test_pre_imaging_uses_named_keys() -> None:
    """Test that pre-imaging offsets are keyed by name."""
    serializer = ImagingVariantSerializer(
        data={
            "variant": "PRE_IMAGING",
            "preImagingOffsets": [
                offset(1.5, -1.5),
                offset(0.0, 0.0),
                offset(4.0, -6.0),
                offset(8.0, 0.0),
            ],
        }
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {
        "preImaging": {
            "offset1": offset(1.5, -1.5),
            "offset2": offset(0.0, 0.0),
            "offset3": offset(4.0, -6.0),
            "offset4": offset(8.0, 0.0),
        }
    }


def test_empty_pre_imaging_offset_is_not_sent() -> None:
    """Test that an offset left empty in the form is omitted, not sent as zero."""
    serializer = ImagingVariantSerializer(
        data={
            "variant": "PRE_IMAGING",
            "preImagingOffsets": [
                offset(1.5, -1.5),
                offset(None, None),
                offset(0.0, 0.0),
                offset(None, None),
            ],
        }
    )
    assert serializer.is_valid(), serializer.errors

    formatted = serializer.format_gpp()["preImaging"]
    assert set(formatted) == {"offset1", "offset3"}
    # A real zero is kept; only the empty ones disappear.
    assert formatted["offset3"] == offset(0.0, 0.0)


@pytest.mark.parametrize(
    "overrides, expected_field",
    [
        ({"offsets": "SPIRAL", "spiralSize": None}, "offsets"),
        ({"offsets": "RANDOM", "spiralSize": None}, "offsets"),
        ({"offsets": "UNIFORM", "spiralSize": None}, "offsets"),
        ({"offsets": "ENUMERATED", "spiralSize": None}, "offsets"),
        ({"skyOffsets": "SPIRAL"}, "skyOffsets"),
        ({"skyOffsets": "ENUMERATED"}, "skyOffsets"),
    ],
)
def test_generator_without_parameters_is_rejected(
    overrides: dict, expected_field: str
) -> None:
    """Test that a generator missing its parameters raises a validation error."""
    serializer = ImagingVariantSerializer(data=grouped(**overrides))
    assert not serializer.is_valid()
    assert expected_field in serializer.errors


@pytest.mark.parametrize(
    "data, expected_field",
    [
        ({}, "variant"),
        ({"variant": "GMOS_NORTH"}, "variant"),
        (grouped(offsets="TRIANGLE"), "offsets"),
        (grouped(wavelengthOrder="SIDEWAYS"), "wavelengthOrder"),
        (grouped(skyOffsetCount=-1), "skyOffsetCount"),
    ],
)
def test_invalid_inputs(data: dict, expected_field: str) -> None:
    """Test that invalid values raise the expected validation errors."""
    serializer = ImagingVariantSerializer(data=data)
    assert not serializer.is_valid()
    assert expected_field in serializer.errors


def test_to_pydantic_outputs_valid_model() -> None:
    """Test that to_pydantic returns a valid ImagingVariantInput."""
    serializer = ImagingVariantSerializer(data=grouped())
    assert serializer.is_valid(), serializer.errors

    model = serializer.to_pydantic()
    assert model.model_dump(exclude_none=True) == {
        "grouped": {
            "order": "DECREASING",
            "sky_count": 2,
            "offsets": {"spiral": {"size": {"arcseconds": 10.0}}},
        }
    }


def test_half_filled_pre_imaging_offset_is_rejected() -> None:
    """Test that an offset with only one axis raises instead of inventing a zero."""
    serializer = ImagingVariantSerializer(
        data={
            "variant": "PRE_IMAGING",
            "preImagingOffsets": [offset(None, 5.0)],
        }
    )
    assert not serializer.is_valid()
    assert "preImagingOffsets" in serializer.errors


def test_more_than_four_pre_imaging_offsets_is_rejected() -> None:
    """Test that extra offsets are rejected rather than silently truncated."""
    serializer = ImagingVariantSerializer(
        data={
            "variant": "PRE_IMAGING",
            "preImagingOffsets": [offset(float(i), float(i)) for i in range(5)],
        }
    )
    assert not serializer.is_valid()
    assert "preImagingOffsets" in serializer.errors


@pytest.mark.parametrize(
    "size_field, generator",
    [
        ("spiralSize", "SPIRAL"),
        ("randomSize", "RANDOM"),
    ],
)
def test_negative_generator_size_is_rejected(size_field: str, generator: str) -> None:
    """Test that a negative size is rejected: a size is a length."""
    overrides = {"offsets": generator, "spiralSize": None, size_field: -5.0}
    serializer = ImagingVariantSerializer(data=grouped(**overrides))
    assert not serializer.is_valid()
    assert size_field in serializer.errors


def test_zero_size_is_accepted() -> None:
    """Test that a zero size still passes: only negatives are meaningless."""
    serializer = ImagingVariantSerializer(data=grouped(spiralSize=0.0))
    assert serializer.is_valid(), serializer.errors
    assert serializer.format_gpp()["grouped"]["offsets"] == {
        "spiral": {"size": {"arcseconds": 0.0}}
    }
