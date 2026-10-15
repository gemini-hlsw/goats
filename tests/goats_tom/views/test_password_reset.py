"""Tests for resetting a forgotten password by email."""

import re

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from goats_tom.accounts import create_account_request
from goats_tom.models import OutgoingEmail
from goats_tom.tests.factories import UserFactory

PAGE = reverse("password_reset")


def _reset_link(email: OutgoingEmail) -> str:
    return re.search(r"https?://\S+/accounts/reset/\S+/", email.body).group(0)


@pytest.mark.django_db
def test_a_user_resets_their_password_through_the_emailed_link(client):
    UserFactory(username="grace", email="grace@example.org")

    response = client.post(PAGE, {"email": "GRACE@example.org"})

    assert response.url == reverse("password_reset_done")
    email = OutgoingEmail.objects.get()
    assert email.to == "grace@example.org"
    assert email.subject == "[GOATS] Reset your GOATS password"
    link = _reset_link(email)
    assert link.startswith("http://testserver/accounts/reset/")

    # Django swaps the token for a session marker and redirects to the form.
    form_page = client.get(link, follow=True)
    assert form_page.context["validlink"]
    client.post(
        form_page.redirect_chain[-1][0],
        {"new_password1": "a-brand-new-pass", "new_password2": "a-brand-new-pass"},
    )
    assert User.objects.get(username="grace").check_password("a-brand-new-pass")


@pytest.mark.django_db
def test_an_unknown_address_looks_the_same_and_sends_nothing(client):
    response = client.post(PAGE, {"email": "nobody@example.org"})

    assert response.url == reverse("password_reset_done")
    assert not OutgoingEmail.objects.exists()


@pytest.mark.django_db
def test_a_pending_applicant_cannot_reset(client):
    user = User(username="ada", email="ada@example.org")
    user.set_password("an-analytical-engine")
    create_account_request(user)

    client.post(PAGE, {"email": "ada@example.org"})

    assert not OutgoingEmail.objects.filter(to="ada@example.org").exists()


@pytest.mark.django_db
@override_settings(GOATS_SITE_URL="https://goats.example.org")
def test_the_link_uses_the_site_url(client):
    UserFactory(email="grace@example.org")

    client.post(PAGE, {"email": "grace@example.org"})

    link = _reset_link(OutgoingEmail.objects.get())
    assert link.startswith("https://goats.example.org/accounts/reset/")


@pytest.mark.django_db
@override_settings(GOATS_SEND_EMAIL=False)
def test_the_page_is_not_offered_without_email(client):
    assert client.get(PAGE).status_code == 404


@pytest.mark.django_db
def test_a_used_link_is_refused(client):
    content = client.get(
        reverse("password_reset_confirm", args=["MQ", "set-password"]), follow=True
    ).content.decode()

    assert "This link is invalid or has already been used." in content
