import pytest
from gpp_client.generated.enums import GuideState

from goats_tom.serializers.gpp.instruments import SlitTelescopeConfigsSerializer


def along_slit_config(q: float, guiding: str = "ENABLED") -> dict:
    """Build one along slit config the form emits."""
    return {"q": {"arcseconds": q}, "guiding": guiding}


def to_sky_config(p: float, q: float, guiding: str = "ENABLED") -> dict:
    """Build one to sky config the form emits."""
    return {"offset": {"p": {"arcseconds": p}, "q": {"arcseconds": q}}, "guiding": guiding}


def test_along_slit_formats_for_gpp() -> None:
    """Test that along slit offsets keep their q and guide state."""
    serializer = SlitTelescopeConfigsSerializer(
        data={
            "offsetMode": "NOD_ALONG_SLIT",
            "alongSlit": [along_slit_config(0.0), along_slit_config(15.0, "DISABLED")],
        }
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {
        "alongSlit": [
            {"q": {"arcseconds": 0.0}, "guiding": "ENABLED"},
            {"q": {"arcseconds": 15.0}, "guiding": "DISABLED"},
        ]
    }


def test_to_sky_formats_for_gpp() -> None:
    """Test that to sky offsets keep their p, q and guide state."""
    serializer = SlitTelescopeConfigsSerializer(
        data={
            "offsetMode": "NOD_TO_SKY",
            "toSky": [to_sky_config(0.0, 0.0), to_sky_config(30.0, 0.0, "DISABLED")],
        }
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {
        "toSky": [
            {
                "offset": {"p": {"arcseconds": 0.0}, "q": {"arcseconds": 0.0}},
                "guiding": "ENABLED",
            },
            {
                "offset": {"p": {"arcseconds": 30.0}, "q": {"arcseconds": 0.0}},
                "guiding": "DISABLED",
            },
        ]
    }


def test_only_the_chosen_mode_is_sent() -> None:
    """Test that the offsets of the other mode are left out."""
    serializer = SlitTelescopeConfigsSerializer(
        data={
            "offsetMode": "NOD_TO_SKY",
            "alongSlit": [along_slit_config(15.0)],
            "toSky": [to_sky_config(0.0, 0.0)],
        }
    )
    assert serializer.is_valid(), serializer.errors

    assert list(serializer.format_gpp()) == ["toSky"]


@pytest.mark.parametrize(
    "data, expected_field",
    [
        ({"offsetMode": "NOD_ALONG_SLIT", "alongSlit": []}, "alongSlit"),
        ({"offsetMode": "NOD_TO_SKY", "alongSlit": [along_slit_config(0.0)]}, "toSky"),
        ({"offsetMode": "SIDEWAYS", "alongSlit": [along_slit_config(0.0)]}, "offsetMode"),
        (
            {"offsetMode": "NOD_ALONG_SLIT", "alongSlit": [along_slit_config(None)]},
            "alongSlit",
        ),
        (
            {"offsetMode": "NOD_TO_SKY", "toSky": [to_sky_config(0.0, 0.0, "MAYBE")]},
            "toSky",
        ),
    ],
)
def test_invalid_offsets_are_rejected(data: dict, expected_field: str) -> None:
    """Test that missing, empty or malformed offsets are rejected."""
    serializer = SlitTelescopeConfigsSerializer(data=data)
    assert not serializer.is_valid()
    assert expected_field in serializer.errors


def test_to_pydantic_outputs_valid_model() -> None:
    """Test that the payload builds a ``SlitTelescopeConfigsInput``."""
    serializer = SlitTelescopeConfigsSerializer(
        data={"offsetMode": "NOD_TO_SKY", "toSky": [to_sky_config(1.5, -2.0)]}
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.to_pydantic().model_dump(exclude_none=True) == {
        "to_sky": [
            {
                "offset": {"p": {"arcseconds": 1.5}, "q": {"arcseconds": -2.0}},
                "guiding": GuideState.ENABLED,
            }
        ]
    }
