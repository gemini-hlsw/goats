"""The GOATS BLANCO form: what it asks, what it sends and what it refuses.

The vendored form hard-codes NEWFIRM's parameters and sends them whatever
the instrument. What is tested here is that the chosen instrument decides:
its own parameters are asked for, its own values are accepted, and nothing
else reaches the portal.
"""

import json
from pathlib import Path

import pytest
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.facilities import BLANCOFacility
from goats_tom.facilities import instrument_schema as schema

INSTRUMENTS = json.loads(
    (
        Path(__file__).parent.parent.parent / "data" / "blanco_instruments.json"
    ).read_text()
)
DECAM = "BLANCO_DECAM"
NEWFIRM = "BLANCO_NEWFIRM"


@pytest.fixture(autouse=True)
def _portal(mocker):
    """Keep the form's lookups, and its validation, off the network."""
    for name in ("_get_instruments", "get_instruments"):
        mocker.patch(
            f"tom_observations.facilities.ocs.OCSBaseForm.{name}",
            return_value=INSTRUMENTS,
        )
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseForm.proposal_choices",
        return_value=[("1", "Test (1)")],
    )
    # The toolkit asks the portal on every is_valid(), whatever it holds.
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseObservationForm.validate_at_facility"
    )


@pytest.fixture()
def form_class(db):
    return BLANCOFacility().get_form("IMAGING")


@pytest.fixture()
def target(db):
    return SiderealTargetFactory.create()


def filled(target, **fields):
    """One configuration of one exposure, enough to build a request from."""
    return {
        "name": "a request",
        "proposal": "1",
        "ipp_value": "1.05",
        "observation_mode": "NORMAL",
        "start": "2026-09-01 20:00:00",
        "end": "2026-09-02 06:00:00",
        "facility": "BLANCO",
        "observation_type": "IMAGING",
        "target_id": target.id,
        "c_1_instrument_type": NEWFIRM,
        "c_1_configuration_type": "EXPOSE",
        "c_1_max_airmass": "1.6",
        "c_1_ic_1_exposure_count": "1",
        "c_1_ic_1_exposure_time": "20",
        "c_1_ic_1_filter": "JX",
        # NEWFIRM declares its coadds required.
        "c_1_ic_1_extra_coadds": "1",
        **fields,
    }


# -- what the form asks for --------------------------------------------------


def test_the_vendored_parameters_are_gone(form_class):
    """They are NEWFIRM's, and the vendored form asked them of DECam too."""
    fields = form_class().fields

    for name in ("dither_value", "dither_sequence", "detector_centering"):
        assert f"c_1_{name}" not in fields


def test_a_field_is_offered_for_every_parameter_any_instrument_declares(form_class):
    """The instrument is not known until it is picked, so both are drawn."""
    fields = form_class().fields
    extra = schema.EXTRA

    assert f"c_1_{extra}_detector_centering" in fields
    assert f"c_1_{extra}_dither_sequence" in fields
    assert f"c_1_ic_1_{extra}_coadds" in fields


def test_the_offsets_the_portal_asks_for_are_added(form_class):
    """The toolkit's form has no field for them."""
    fields = form_class().fields

    assert fields["c_1_ic_1_offset_ra"].label == "Offset Right Ascension"
    assert fields["c_1_ic_1_offset_dec"].label == "Offset Declination"


def test_the_fields_are_called_what_the_portal_calls_them(form_class):
    fields = form_class().fields

    assert fields["observation_mode"].label == "Mode"
    assert fields["ipp_value"].label == "IPP Factor"
    assert fields["c_1_instrument_type"].label == "Instrument"
    assert fields["c_1_min_lunar_distance"].label == "Minimum Lunar Separation"


def test_a_field_says_what_it_is_measured_in(form_class):
    """Beside the control, the way the GPP form shows its own."""
    fields = form_class().fields

    assert fields["c_1_ic_1_exposure_time"].widget.attrs["data-unit"] == "s"
    assert fields["acceptability_threshold"].widget.attrs["data-unit"] == "%"
    # The unit is beside the control now, not inside it.
    assert "placeholder" not in fields["c_1_ic_1_offset_ra"].widget.attrs


def test_the_cadence_is_explained_as_more_than_decimal_hours(form_class):
    """The toolkit's help says only what the unit already says."""
    assert "replaces the window" in form_class().fields["period"].help_text


def test_an_option_does_not_repeat_what_the_form_already_says(form_class):
    """Every instrument here is on the same telescope, and names itself."""
    fields = form_class().fields

    assert [label for _, label in fields["c_1_instrument_type"].choices] == [
        "DECam",
        "NEWFIRM",
    ]
    assert "Fowler-1" in [
        label for _, label in fields["c_1_ic_1_readout_mode"].choices
    ]


def test_a_filter_keeps_the_whole_of_its_name(form_class):
    """`r` is the whole of what a filter is called."""
    labels = [label for _, label in form_class().fields["c_1_ic_1_filter"].choices]

    assert "r" in labels


def test_the_threshold_the_instruments_settle_for_is_offered(form_class):
    """The portal's own form comes with it filled in."""
    assert form_class().fields["acceptability_threshold"].initial == 90.0


# -- what the form sends -----------------------------------------------------


def test_only_the_chosen_instrument_s_parameters_are_sent(form_class, target):
    """DECam rejects the coadds and the dither the vendored form sends it."""
    form = form_class(data=filled(target, c_1_instrument_type=DECAM))
    assert form.is_valid(), form.errors

    configuration = form.observation_payload()["requests"][0]["configurations"][0]

    assert set(configuration["extra_params"]) == {"detector_centering"}
    assert configuration["instrument_configs"][0]["extra_params"] == {}


def test_what_an_instrument_declares_is_sent_with_its_defaults(form_class, target):
    form = form_class(data=filled(target))
    assert form.is_valid(), form.errors

    configuration = form.observation_payload()["requests"][0]["configurations"][0]

    assert configuration["extra_params"]["dither_sequence"] == "2x2"
    assert configuration["extra_params"]["dither_value"] == 80
    assert configuration["instrument_configs"][0]["extra_params"]["coadds"] == 1


def test_an_offset_is_left_out_when_it_is_left_blank(form_class, target):
    """An unoffset exposure is an exposure with no offset, not one of zero."""
    form = form_class(data=filled(target))
    assert form.is_valid(), form.errors
    unoffset = form.observation_payload()["requests"][0]["configurations"][0]

    offset = form_class(data=filled(target, c_1_ic_1_offset_ra="1.5"))
    assert offset.is_valid(), offset.errors
    moved = offset.observation_payload()["requests"][0]["configurations"][0]

    assert "offset_ra" not in unoffset["instrument_configs"][0]
    assert moved["instrument_configs"][0]["offset_ra"] == 1.5


def test_the_acceptability_threshold_reaches_the_request(form_class, target):
    form = form_class(data=filled(target, acceptability_threshold="80"))
    assert form.is_valid(), form.errors

    request = form.observation_payload()["requests"][0]

    assert request["acceptability_threshold"] == 80


# -- what the form refuses ---------------------------------------------------


def test_an_exposure_with_no_time_is_refused(form_class, target):
    """Unrefused it is dropped, and the configuration is dropped after it."""
    form = form_class(data=filled(target, c_1_ic_1_exposure_time=""))

    assert not form.is_valid()
    assert "c_1_ic_1_exposure_time" in form.errors


def test_a_parameter_an_instrument_insists_on_is_refused_empty(form_class, target):
    """NEWFIRM declares its coadds required; DECam has none to declare."""
    without = filled(target, c_1_ic_1_extra_coadds="")

    assert "c_1_ic_1_extra_coadds" in form_class(data=without).errors
    assert "c_1_ic_1_extra_coadds" not in form_class(
        data={**without, "c_1_instrument_type": DECAM}
    ).errors


def test_an_exposure_never_drawn_is_never_asked_for(form_class, target):
    """A field is declared for every exposure the facility allows."""
    errors = form_class(data=filled(target)).errors

    assert not [name for name in errors if name.startswith("c_2")]
    assert "c_1_ic_2_exposure_time" not in errors


def test_a_value_the_chosen_instrument_will_not_take_is_refused(form_class, target):
    """The field offers what either takes; only one of them is observing."""
    extra = schema.EXTRA
    form = form_class(
        data=filled(target, **{f"c_1_{extra}_detector_centering": "central_gap"})
    )

    assert not form.is_valid()
    assert "not accepted by this instrument" in str(
        form.errors[f"c_1_{extra}_detector_centering"]
    )


def test_a_bound_the_chosen_instrument_sets_is_refused(form_class, target):
    """NEWFIRM will not expose for longer than 40 seconds."""
    form = form_class(data=filled(target, c_1_ic_1_exposure_time="120"))

    assert not form.is_valid()
    assert "more than 40" in str(form.errors["c_1_ic_1_exposure_time"])
    assert form_class(
        data=filled(target, c_1_instrument_type=DECAM, c_1_ic_1_exposure_time="120")
    ).is_valid()


def test_a_configuration_observes_the_target_substituted_for_it(form_class, target):
    """The toolkit builds the target block; what it builds it from is ours."""
    from tom_targets.models import TargetList

    companion = SiderealTargetFactory.create(name="the other one")
    group = TargetList.objects.create(name="a group")
    group.targets.set([target, companion])

    form = form_class(data=filled(target, c_1_target_override=str(companion.id)))
    assert form.is_valid(), form.errors

    configuration = form.observation_payload()["requests"][0]["configurations"][0]

    assert configuration["target"]["name"] == "the other one"


def test_a_configuration_left_alone_observes_the_request_s_target(form_class, target):
    form = form_class(data=filled(target))
    assert form.is_valid(), form.errors

    configuration = form.observation_payload()["requests"][0]["configurations"][0]

    assert configuration["target"]["name"] == target.name
