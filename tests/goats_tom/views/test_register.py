"""Tests for the public page to request an account."""

import re

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.models import AccountRequest
from goats_tom.tests.factories import UserFactory

PAGE = reverse("register")


def _data(**overrides):
    data = {
        "username": "ada",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.org",
        "affiliation": "NOIRLab",
        "password1": "an-analytical-engine",
        "password2": "an-analytical-engine",
        "message": "Working on follow-up.",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_the_form_offers_no_groups(client):
    response = client.get(PAGE)

    assert response.status_code == 200
    assert "groups" not in response.context["form"].fields


@pytest.mark.django_db
def test_requesting_creates_an_inactive_account_awaiting_approval(client):
    response = client.post(PAGE, _data())

    assert response.status_code == 302
    assert response.url == reverse("register-done")
    user = User.objects.get(username="ada")
    assert not user.is_active
    assert user.check_password("an-analytical-engine")
    assert user.profile.affiliation == "NOIRLab"
    assert user.account_request.status == AccountRequest.STATUS_PENDING
    assert user.account_request.message == "Working on follow-up."


@pytest.mark.django_db
def test_groups_cannot_be_chosen_by_the_applicant(client):
    group = Group.objects.create(name="Gemini")

    client.post(PAGE, _data(groups=[group.pk]))

    assert not User.objects.get(username="ada").groups.exists()


@pytest.mark.django_db
def test_an_address_already_in_use_is_refused(client):
    UserFactory(email="Ada@Example.org")

    response = client.post(PAGE, _data())

    assert response.status_code == 200
    assert "An account with this email address already exists." in (
        response.content.decode()
    )
    assert not AccountRequest.objects.exists()


@pytest.mark.django_db
def test_a_message_of_200_words_is_accepted(client):
    message = " ".join(["word"] * 200)

    response = client.post(PAGE, _data(message=message))

    assert response.status_code == 302
    assert AccountRequest.objects.get().message == message


@pytest.mark.django_db
def test_a_message_over_200_words_is_refused(client):
    response = client.post(PAGE, _data(message=" ".join(["word"] * 201)))

    assert response.status_code == 200
    assert "at most 200 words (it has 201)." in response.content.decode()
    assert not AccountRequest.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("submit", [False, True], ids=["empty", "with-errors"])
def test_every_field_description_is_on_the_page(client, submit):
    response = client.post(PAGE, _data(email="nope")) if submit else client.get(PAGE)
    content = response.content.decode()

    ids = set(re.findall(r'\bid="([^"]+)"', content))
    described = re.findall(r'aria-describedby="([^"]+)"', content)
    assert described
    for refs in described:
        assert set(refs.split()) <= ids, refs


@pytest.mark.django_db
def test_required_fields_are_marked(client):
    content = client.get(PAGE).content.decode()

    assert re.search(r'>Username<span class="text-danger"[^>]*>\*</span>', content)
    assert re.search(r">Why do you need access\? \(optional\)</label>", content)


@pytest.mark.django_db
def test_a_signed_in_user_is_sent_home(client):
    client.force_login(UserFactory())

    response = client.get(PAGE)

    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_the_done_page_explains_what_happens_next(client):
    content = client.get(reverse("register-done")).content.decode()

    assert "Awaiting approval." in content
