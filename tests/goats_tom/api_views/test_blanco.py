import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _portal(mocker):
    """Keep the form's lookups off the network."""
    # The proposals are cached for an hour, and the cache outlives a test.
    cache.clear()
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseForm._get_instruments",
        return_value={},
    )
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseForm.get_instruments",
        return_value={},
    )
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseForm.proposal_choices",
        return_value=[("1", "Test (1)")],
    )


@pytest.fixture()
def client(db):
    api = APIClient()
    api.force_authenticate(user=UserFactory.create())
    return api


@pytest.fixture()
def target(db):
    return SiderealTargetFactory.create()


@pytest.mark.django_db()
def test_details_is_the_first_section_and_starts_open(client, target):
    """The form opens on what the request is, before anything is configured."""
    response = client.get(reverse("blancoobservations-list"), {"target_id": target.id})

    assert response.status_code == 200
    section = response.json()["sections"][0]
    assert section["title"] == "Details"
    assert section["open"] is True


@pytest.mark.django_db()
def test_details_asks_for_what_the_portal_asks_above_the_configurations(
    client, target
):
    """Name, proposal, mode and IPP, then the three request fields."""
    response = client.get(reverse("blancoobservations-list"), {"target_id": target.id})

    names = [field["name"] for field in response.json()["sections"][0]["fields"]]

    assert names == [
        "name",
        "proposal",
        "observation_mode",
        "ipp_value",
        "acceptability_threshold",
        "configuration_repeats",
        "optimization_type",
    ]


@pytest.mark.django_db()
def test_every_field_is_half_a_row_or_a_whole_one(client, target):
    """The form has no other width."""
    fields = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][0]["fields"]

    assert {field["width"] for field in fields} <= {6, 12}


@pytest.mark.django_db()
def test_a_choice_field_arrives_with_its_options(client, target):
    """The interface never invents what the form accepts."""
    fields = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][0]["fields"]

    mode = next(field for field in fields if field["name"] == "observation_mode")

    assert mode["type"] == "choice"
    assert [choice["value"] for choice in mode["choices"]] == [
        "NORMAL",
        "RAPID_RESPONSE",
        "TIME_CRITICAL",
    ]


@pytest.mark.django_db()
def test_the_acceptability_threshold_is_ours_to_add(client, target):
    """The vendored form has no such field; the portal's own asks for it."""
    fields = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][0]["fields"]

    threshold = next(
        field for field in fields if field["name"] == "acceptability_threshold"
    )

    assert threshold["type"] == "float"
    assert threshold["max"] == 100


@pytest.mark.django_db()
def test_a_target_is_required(client):
    assert client.get(reverse("blancoobservations-list")).status_code == 400


@pytest.mark.django_db()
def test_an_unknown_target_is_not_found(client):
    response = client.get(reverse("blancoobservations-list"), {"target_id": 9999})

    assert response.status_code == 404


@pytest.mark.django_db()
def test_the_form_is_not_served_to_anyone(client):
    """The facility acts for a user, whose API key it uses."""
    assert APIClient().get(reverse("blancoobservations-list")).status_code in (401, 403)


@pytest.mark.django_db()
def test_the_sections_are_served_in_reading_order(client, target):
    """What is asked, then what is done, then when it may be done."""
    response = client.get(reverse("blancoobservations-list"), {"target_id": target.id})

    titles = [section["title"] for section in response.json()["sections"]]

    assert titles == ["Details", "Configuration", "Window"]


@pytest.mark.django_db()
def test_the_window_carries_the_cadence_that_would_replace_it(client, target):
    """A cadence is not a second window: filling it in drops the window."""
    window = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][2]

    assert [field["name"] for field in window["fields"]] == ["start", "end"]
    assert window["sections"][0]["title"] == "Cadence"
    assert [field["name"] for field in window["sections"][0]["fields"]] == [
        "period",
        "jitter",
    ]


@pytest.mark.django_db()
def test_a_configuration_holds_its_exposures_and_its_constraints(client, target):
    """The portal puts them inside the configuration they belong to."""
    configuration = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][1]

    assert configuration["repeat"] == "configuration"
    assert [section["title"] for section in configuration["instances"][0]["sections"]] == [
        "Exposures",
        "Constraints",
    ]


@pytest.mark.django_db()
def test_every_configuration_the_facility_allows_is_described(client, target):
    """The interface draws the first and adds the rest as they are asked for."""
    configuration = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][1]

    assert len(configuration["instances"]) > 1
    assert [instance["id"] for instance in configuration["instances"]][0] == 1


@pytest.mark.django_db()
def test_an_exposure_says_what_cannot_be_left_out(client, target):
    """The field cannot be required of every exposure, only of the ones drawn."""
    exposure = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][1]["instances"][0]["sections"][0]["instances"][0]

    required = {field["name"] for field in exposure["fields"] if field["required"]}

    assert "c_1_ic_1_exposure_time" in required
    assert "c_1_ic_1_offset_ra" not in required


@pytest.mark.django_db()
def test_what_the_toolkit_s_own_view_asks_for_is_served_too(client, target):
    """The interface posts them back untouched when it submits."""
    hidden = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["hidden"]

    assert hidden == {
        "facility": "BLANCO",
        "observation_type": "IMAGING",
        "target_id": str(target.id),
    }


@pytest.mark.django_db()
def test_a_form_with_nothing_in_it_comes_back_with_what_it_is_missing(client, target):
    """Checked here first: the toolkit asks the portal whatever it holds, and
    builds the payload to ask with, so an empty form raises instead."""
    response = client.post(
        reverse("blancoobservations-list"),
        {"target_id": target.id, "fields": {}},
        format="json",
    )

    body = response.json()

    assert body["valid"] is False
    assert body["errors"]["name"] == ["This field is required."]


@pytest.mark.django_db()
def test_a_form_the_portal_accepts_says_so(client, target, mocker):
    mocker.patch(
        "tom_observations.facilities.ocs.OCSBaseObservationForm.validate_at_facility"
    )
    mocker.patch(
        "tom_observations.facilities.ocs.OCSFullObservationForm.get_validation_message",
        return_value="This observation is valid.",
    )

    response = client.post(
        reverse("blancoobservations-list"),
        {
            "target_id": target.id,
            "fields": {
                "name": "a request",
                "proposal": "1",
                "ipp_value": "1.05",
                "observation_mode": "NORMAL",
                "start": "2026-09-01 20:00:00",
                "end": "2026-09-02 06:00:00",
                "c_1_instrument_type": "",
                "c_1_max_airmass": "1.6",
            },
        },
        format="json",
    )

    assert response.json() == {"valid": True, "message": "This observation is valid."}


@pytest.mark.django_db()
def test_a_check_needs_a_target_like_everything_else(client):
    response = client.post(
        reverse("blancoobservations-list"), {"fields": {}}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db()
def test_a_configuration_can_be_given_a_target_of_its_own(client, target):
    """The portal lets a configuration observe another target of the group,
    which is what a request of several configurations is usually for."""
    from tom_targets.models import TargetList

    companion = SiderealTargetFactory.create(name="the other one")
    group = TargetList.objects.create(name="a group")
    group.targets.set([target, companion])

    configuration = client.get(
        reverse("blancoobservations-list"), {"target_id": target.id}
    ).json()["sections"][1]["instances"][0]

    override = next(
        field
        for field in configuration["fields"]
        if field["name"] == "c_1_target_override"
    )

    assert override["label"] == "Target"
    assert [choice["label"] for choice in override["choices"]] == [
        target.name,
        "the other one",
    ]


@pytest.mark.django_db()
def test_a_target_that_keeps_no_company_is_not_asked_to_be_substituted(client, target):
    """The only target on offer would be the one the request already names."""
    names = [
        field["name"]
        for field in client.get(
            reverse("blancoobservations-list"), {"target_id": target.id}
        ).json()["sections"][1]["instances"][0]["fields"]
    ]

    assert "c_1_target_override" not in names


@pytest.mark.django_db()
def test_what_a_proposal_may_be_observed_with_reaches_the_interface(
    client, target, mocker
):
    """Time given on one instrument cannot be spent on another."""
    mocker.patch(
        "goats_tom.facilities.blanco.GOATSBLANCOImagingObservationForm"
        ".instruments_by_proposal",
        return_value={"1": ["BLANCO_DECAM"]},
    )

    response = client.get(reverse("blancoobservations-list"), {"target_id": target.id})

    assert response.json()["proposals"] == {"1": ["BLANCO_DECAM"]}
