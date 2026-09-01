"""What the portal's own schema says an instrument takes.

The fixture is the answer ``https://observe.lco.global/api/instruments/``
gives for BLANCO: DECam, which centres on one of three detectors and does
not dither at all, and NEWFIRM, which dithers through a sequence, coadds,
and will not expose for longer than 40 seconds.
"""

import json
from pathlib import Path

import pytest
from django import forms

from goats_tom.facilities import instrument_schema as schema

INSTRUMENTS = json.loads(
    (Path(__file__).parent.parent.parent / "data" / "blanco_instruments.json").read_text()
)
DECAM = INSTRUMENTS["BLANCO_DECAM"]
NEWFIRM = INSTRUMENTS["BLANCO_NEWFIRM"]


def test_a_configuration_takes_what_its_instrument_declares():
    assert set(schema.configuration_parameters(DECAM)) == {"detector_centering"}
    assert set(schema.configuration_parameters(NEWFIRM)) == {
        "detector_centering",
        "dither_sequence",
        "dither_sequence_random_offset",
        "dither_value",
    }


def test_an_exposure_takes_what_its_instrument_declares():
    """DECam declares none of NEWFIRM's, which the vendored form sends anyway."""
    assert schema.exposure_parameters(DECAM) == {}
    assert set(schema.exposure_parameters(NEWFIRM)) == {"coadds", "sequence_repeats"}


def test_an_instrument_can_bound_a_field_the_form_already_has():
    """NEWFIRM will not expose for longer than 40 seconds; DECam says nothing."""
    assert schema.base_bounds(NEWFIRM)["exposure_time"]["max"] == 40
    assert schema.base_bounds(DECAM) == {}


def test_narrowing_is_keyed_by_what_a_field_name_ends_in():
    """The interface knows a field by its suffix, whatever configuration it sits in."""
    narrowed = schema.narrowing(NEWFIRM)

    assert narrowed[f"{schema.EXTRA}_dither_sequence"]["allowed"] == [
        "2x2",
        "3x3",
        "4x4",
        "5-point",
    ]
    assert narrowed["filter"]["allowed"] == ["JX", "HX", "KXs"]
    assert narrowed["readout_mode"]["allowed"] == ["fowler1", "fowler2"]
    assert narrowed["configuration_type"]["allowed"] == [
        "DARK",
        "EXPOSE",
        "SKY",
        "SKY_FLAT",
        "STANDARD",
    ]


def test_narrowing_leaves_out_what_an_instrument_never_declared():
    """DECam has no dither, so the interface hides the fields for one."""
    narrowed = schema.narrowing(DECAM)

    assert f"{schema.EXTRA}_dither_value" not in narrowed
    assert narrowed[f"{schema.EXTRA}_detector_centering"]["allowed"] == [
        "central_gap",
        "N4",
        "S4",
    ]


def test_merging_offers_every_value_any_instrument_takes():
    """One field is drawn for both, and what is really allowed is checked later."""
    merged = schema.merge(
        [
            schema.configuration_parameters(DECAM),
            schema.configuration_parameters(NEWFIRM),
        ]
    )

    assert merged["detector_centering"]["allowed"] == [
        "central_gap",
        "N4",
        "S4",
        "none",
        "det_1",
        "det_2",
        "det_3",
        "det_4",
    ]


def test_a_bound_survives_only_if_every_instrument_sets_one():
    """A field one instrument leaves open is open on the form."""
    both = schema.merge([{"a": {"min": 1, "max": 10}}, {"a": {"min": 2, "max": 40}}])
    one = schema.merge([{"a": {"max": 10}}, {"a": {}}])

    assert both["a"] == {"min": 1, "max": 40}
    assert "max" not in one["a"]


def test_a_parameter_is_called_what_the_portal_calls_it():
    assert schema.label_for("dither_sequence", {"label": "Dither Pattern"}) == (
        "Dither Pattern"
    )


def test_a_parameter_the_portal_never_named_is_titled():
    """"Dither value" beside "Exposure Count" would be two forms in one."""
    assert schema.label_for("dither_value", {}) == "Dither Value"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("central_gap", "Central gap"),
        ("det_1", "Det 1"),
        ("none", "None"),
        # Capitals in a code are there for a reason.
        ("N4", "N4"),
        ("KXs", "KXs"),
        ("2x2", "2x2"),
    ],
)
def test_a_value_is_written_the_way_a_person_would_write_it(value, expected):
    assert schema.readable(value) == expected


def test_a_field_is_built_from_what_the_parameter_is():
    parameters = schema.configuration_parameters(NEWFIRM)
    sequence = schema.build_field("dither_sequence", parameters["dither_sequence"])
    value = schema.build_field("dither_value", parameters["dither_value"])
    offset = schema.build_field(
        "dither_sequence_random_offset", parameters["dither_sequence_random_offset"]
    )

    assert isinstance(sequence, forms.ChoiceField)
    assert sequence.initial == "2x2"
    assert isinstance(value, forms.IntegerField)
    assert (value.min_value, value.max_value) == (0, 1600)
    assert isinstance(offset, forms.BooleanField)


def test_a_field_is_never_required_of_every_instrument():
    """One is declared per configuration, and only the chosen one asks for it."""
    coadds = schema.build_field("coadds", schema.exposure_parameters(NEWFIRM)["coadds"])

    assert coadds.required is False


@pytest.mark.parametrize(
    ("value", "spec", "expected"),
    [
        ("3", {"type": "integer"}, 3),
        ("1.5", {"type": "float"}, 1.5),
        (True, {"type": "boolean"}, True),
        ("2x2", {"type": "string"}, "2x2"),
    ],
)
def test_a_value_is_sent_in_the_shape_the_portal_expects(value, spec, expected):
    assert schema.cast(value, spec) == expected


def test_a_value_outside_what_an_instrument_takes_is_refused():
    dither = schema.configuration_parameters(NEWFIRM)["dither_value"]
    centering = schema.configuration_parameters(DECAM)["detector_centering"]

    assert schema.check(80, dither) is None
    assert "1600" in schema.check(2000, dither)
    assert schema.check("central_gap", centering) is None
    assert "det_1 is not accepted" in schema.check("det_1", centering)
