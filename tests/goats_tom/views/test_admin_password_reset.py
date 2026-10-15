"""Tests for resetting a password through an administrator, without email."""

import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from goats_tom.accounts import approve_password_reset, create_account_request
from goats_tom.middleware.password_change import CHANGE_REQUIRED
from goats_tom.models import Notification, PasswordResetRequest
from goats_tom.tests.factories import UserFactory

PAGE = reverse("password_reset_admin")
DONE = reverse("password_reset_admin_done")
NEW_PASSWORD = reverse("new_password")
REQUESTS = reverse("account-requests")

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("email_off")]


@pytest.fixture
def email_off(settings):
    settings.GOATS_SEND_EMAIL = False


@pytest.fixture
def admin():
    return UserFactory(is_superuser=True)


@pytest.fixture
def grace():
    return UserFactory(username="grace", first_name="Grace", last_name="Hopper")


def _decide(client, reset_request, action):
    return client.post(
        reverse("password-reset-decide", args=[reset_request.pk]), {"action": action}
    )


def _temporary_password(response) -> str:
    return re.search(r'<p class="fs-4"><code>(\w+)</code>', response.content.decode())[
        1
    ]


def _sign_in(client, username, password):
    return client.post(reverse("login"), {"username": username, "password": password})


def test_the_request_page_works_from_any_machine(client):
    assert client.get(PAGE).status_code == 200
    assert client.get(PAGE, REMOTE_ADDR="192.168.1.5").status_code == 200


def test_with_email_the_reset_goes_by_email_instead(client, settings):
    settings.GOATS_SEND_EMAIL = True

    assert client.get(PAGE).status_code == 404
    assert client.get(DONE).status_code == 404


def test_requesting_tells_the_administrators(client, admin, grace):
    response = client.post(PAGE, {"username": "grace"})

    assert response.url == DONE
    reset_request = PasswordResetRequest.objects.get(user=grace)
    assert reset_request.status == PasswordResetRequest.STATUS_PENDING
    notification = Notification.objects.get(kind="password.reset_requested")
    assert notification.recipient == admin
    assert notification.message == "Grace Hopper asked to reset their password."
    assert notification.url.endswith(f"#password-reset-{reset_request.pk}")


def test_an_unknown_username_gets_the_same_answer(client, admin):
    assert client.post(PAGE, {"username": "nobody"}).url == DONE
    assert not PasswordResetRequest.objects.exists()


def test_a_pending_applicant_cannot_ask(client, admin):
    user = User(username="ada", email="ada@example.org")
    user.set_password("an-analytical-engine")
    create_account_request(user)

    client.post(PAGE, {"username": "ada"})

    assert not PasswordResetRequest.objects.exists()


def test_asking_twice_keeps_one_pending_request(client, admin, grace):
    client.post(PAGE, {"username": "grace"})
    response = client.post(PAGE, {"username": "grace"})

    assert response.url == DONE
    assert PasswordResetRequest.objects.filter(user=grace).count() == 1


def test_the_administrator_sees_the_request(client, admin, grace):
    client.post(PAGE, {"username": "grace"})
    client.force_login(admin)

    content = client.get(REQUESTS).content.decode()

    assert "Password resets" in content
    assert 'id="password-reset-' in content


def test_resetting_shows_a_temporary_password_once(client, admin, grace):
    client.post(PAGE, {"username": "grace"})
    reset_request = PasswordResetRequest.objects.get()
    client.force_login(admin)

    response = _decide(client, reset_request, "reset")

    assert response.status_code == 200
    assert "no-cache" in response["Cache-Control"]
    password = _temporary_password(response)
    assert len(password) == 12
    assert User.objects.get(username="grace").check_password(password)
    reset_request.refresh_from_db()
    assert reset_request.status == PasswordResetRequest.STATUS_APPROVED
    assert Notification.objects.get(kind="password.reset_requested").is_read


def test_declining_leaves_the_password_alone(client, admin, grace):
    client.post(PAGE, {"username": "grace"})
    reset_request = PasswordResetRequest.objects.get()
    client.force_login(admin)

    _decide(client, reset_request, "deny")

    reset_request.refresh_from_db()
    assert reset_request.status == PasswordResetRequest.STATUS_DENIED
    assert User.objects.get(username="grace").check_password("password")


def test_a_decided_reset_is_not_decided_again(client, admin, grace):
    client.post(PAGE, {"username": "grace"})
    reset_request = PasswordResetRequest.objects.get()
    approve_password_reset(reset_request, admin)
    client.force_login(admin)

    response = client.post(
        reverse("password-reset-decide", args=[reset_request.pk]),
        {"action": "reset"},
        follow=True,
    )

    assert "already been decided" in response.content.decode()


def test_a_non_administrator_cannot_reset(client, grace):
    client.post(PAGE, {"username": "grace"})
    client.force_login(UserFactory())

    response = _decide(client, PasswordResetRequest.objects.get(), "reset")

    assert response.status_code == 403
    assert User.objects.get(username="grace").check_password("password")


def _with_temporary_password(admin, grace) -> str:
    reset_request = PasswordResetRequest.objects.create(user=grace)
    return approve_password_reset(reset_request, admin)


def test_signing_in_with_the_temporary_password_asks_for_a_new_one(
    client, admin, grace
):
    password = _with_temporary_password(admin, grace)

    response = _sign_in(client, "grace", password)

    assert response.url == NEW_PASSWORD
    assert client.get(reverse("home")).url == NEW_PASSWORD


def test_choosing_a_new_password_completes_the_reset(client, admin, grace):
    _sign_in(client, "grace", _with_temporary_password(admin, grace))

    response = client.post(
        NEW_PASSWORD,
        {"new_password1": "a-brand-new-pass", "new_password2": "a-brand-new-pass"},
    )

    assert response.url == reverse("home")
    assert CHANGE_REQUIRED not in client.session
    assert client.get(reverse("home")).status_code == 200
    assert PasswordResetRequest.objects.get().status == (
        PasswordResetRequest.STATUS_COMPLETED
    )
    client.logout()
    assert _sign_in(client, "grace", "a-brand-new-pass").url != NEW_PASSWORD


def test_the_temporary_password_cannot_be_kept(client, admin, grace):
    password = _with_temporary_password(admin, grace)
    _sign_in(client, "grace", password)

    response = client.post(
        NEW_PASSWORD, {"new_password1": password, "new_password2": password}
    )

    assert "Choose a password other than the temporary one." in (
        response.content.decode()
    )


def test_an_ordinary_sign_in_is_unaffected(client, grace):
    response = _sign_in(client, "grace", "password")

    assert response.url != NEW_PASSWORD
    assert CHANGE_REQUIRED not in client.session
