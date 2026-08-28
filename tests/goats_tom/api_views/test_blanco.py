import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _portal(mocker):
    """Keep the form's lookups off the network."""
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
