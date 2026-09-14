"""The GPP form keeps its choices in JavaScript, so they are checked here.

Those lists are copies of GPP enums. When GPP adds or drops a value, a copy
that is not updated offers the user something the backend rejects, which is
what happened with the image quality and cloud extinction presets. These tests
compare each copy against the enum the gpp-client generated from the schema.
"""

import re
from enum import Enum
from pathlib import Path

import pytest
from gpp_client.generated import enums

JS_DIR = Path(__file__).resolve().parents[3] / "src/goats_tom/static/js/gpp"


def _lookup_keys(file_name: str, lookup: str) -> list[str]:
    """Return the keys of a ``Lookups`` map.

    Parameters
    ----------
    file_name : str
        JavaScript file holding the map.
    lookup : str
        Name of the static map.

    Returns
    -------
    list[str]
        The keys the map is written with.
    """
    text = (JS_DIR / file_name).read_text()
    match = re.search(rf"static {lookup} = \{{(.*?)\n  \}};", text, re.S)
    assert match is not None, f"{lookup} not found in {file_name}"
    return re.findall(r"^\s+([A-Z0-9_]+):", match.group(1), re.M)


def _array_values(file_name: str, pattern: str) -> list[str]:
    """Return the strings of a JavaScript array literal.

    Parameters
    ----------
    file_name : str
        JavaScript file holding the array.
    pattern : str
        Regular expression capturing the array body.

    Returns
    -------
    list[str]
        The values the array is written with.
    """
    text = (JS_DIR / file_name).read_text()
    match = re.search(pattern, text, re.S)
    assert match is not None, f"array not found in {file_name}"
    return re.findall(r'"([A-Z0-9_]+)"', match.group(1))


def _field_options(field_id: str) -> list[str]:
    """Return the option values a ``fields.js`` select offers.

    Parameters
    ----------
    field_id : str
        The ``id`` the field is declared with.

    Returns
    -------
    list[str]
        The option values, in the order they are offered.
    """
    text = (JS_DIR / "fields.js").read_text()
    match = re.search(
        rf'id: "{field_id}",(.*?)\n  \}},', text, re.S
    )
    assert match is not None, f"{field_id} not found in fields.js"
    return re.findall(r'value: "([A-Z0-9_]+)"', match.group(1))


@pytest.mark.parametrize(
    "lookup, enum_class",
    [
        ("imageQuality", enums.ImageQualityPreset),
        ("cloudExtinction", enums.CloudExtinctionPreset),
        ("gmosNorthBuiltinFpu", enums.GmosNorthBuiltinFpu),
        ("gmosSouthBuiltinFpu", enums.GmosSouthBuiltinFpu),
        ("gmosRoi", enums.GmosRoi),
        ("gmosBinning", enums.GmosBinning),
        ("gmosReadMode", enums.GmosAmpReadMode),
    ],
)
def test_lookup_matches_the_schema(lookup: str, enum_class: type[Enum]) -> None:
    """Test that a display lookup carries exactly the values GPP defines."""
    assert set(_lookup_keys("lookups.js", lookup)) == {e.value for e in enum_class}


def test_brightness_bands_match_the_schema() -> None:
    """Test that the brightness editor offers every band GPP defines."""
    bands = _array_values(
        "brightnesses_editor.js", r"this\.#bands = options\.bands \?\? \[(.*?)\];"
    )

    assert set(bands) == {e.value for e in enums.Band}


def test_brightness_units_match_the_schema() -> None:
    """Test that the brightness editor offers every unit GPP defines."""
    units = _array_values(
        "brightnesses_editor.js", r"this\.#units = options\.units \?\? \[(.*?)\];"
    )

    assert set(units) == {e.value for e in enums.BrightnessIntegratedUnits}


@pytest.mark.parametrize(
    "field_id, enum_class",
    [
        ("imageQuality", enums.ImageQualityPreset),
        ("cloudExtinction", enums.CloudExtinctionPreset),
        ("skyBackground", enums.SkyBackground),
        ("waterVapor", enums.WaterVapor),
        ("workflowState", enums.ObservationWorkflowState),
        ("posAngleConstraint", enums.PosAngleConstraintMode),
    ],
)
def test_field_offers_what_the_schema_defines(
    field_id: str, enum_class: type[Enum]
) -> None:
    """Test that a select offers exactly the values GPP accepts."""
    assert set(_field_options(field_id)) == {e.value for e in enum_class}
