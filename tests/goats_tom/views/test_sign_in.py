"""Tests for the sign-in page."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from goats_tom.accounts import create_account_request
from goats_tom.tests.factories import UserFactory

PAGE = reverse("login")
PENDING = "Your account is awaiting approval by an administrator."


@pytest.fixture
def applicant(db):
    user = User(username="ada", email="ada@example.org")
    user.set_password("an-analytical-engine")
    create_account_request(user)
    return user


@pytest.mark.django_db
def test_an_approved_user_signs_in(client):
    UserFactory(username="grace")

    response = client.post(PAGE, {"username": "grace", "password": "password"})

    assert response.status_code == 302


@pytest.mark.django_db
def test_an_applicant_is_told_the_account_awaits_approval(client, applicant):
    response = client.post(
        PAGE, {"username": "ada", "password": "an-analytical-engine"}
    )

    assert PENDING in response.content.decode()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_a_wrong_password_does_not_reveal_a_pending_account(client, applicant):
    response = client.post(PAGE, {"username": "ada", "password": "wrong"})

    content = response.content.decode()
    assert PENDING not in content
    assert "Please enter a correct username and password" in content


@pytest.mark.django_db
def test_a_deactivated_account_is_not_called_pending(client):
    UserFactory(username="grace", is_active=False)

    response = client.post(PAGE, {"username": "grace", "password": "password"})

    assert PENDING not in response.content.decode()


@pytest.mark.django_db
def test_the_page_links_to_requesting_an_account(client):
    assert reverse("register") in client.get(PAGE).content.decode()
