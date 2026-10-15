"""Tests for the page where administrators decide account requests."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.accounts import approve_account_request, create_account_request
from goats_tom.models import AccountRequest
from goats_tom.tests.factories import UserFactory

PAGE = reverse("account-requests")


def _request(username="ada", first_name="Ada", last_name="Lovelace"):
    """A pending account request."""
    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=f"{username}@example.org",
    )
    user.set_password("an-analytical-engine")
    return create_account_request(user, message="Working on follow-up.")


def _decide(client, account_request, **data):
    return client.post(
        reverse("account-request-decide", args=[account_request.pk]),
        data,
        follow=True,
    )


@pytest.fixture
def admin(client, db):
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_only_an_administrator_sees_the_page(client):
    assert client.get(PAGE).status_code == 302

    client.force_login(UserFactory())
    assert client.get(PAGE).status_code == 403


@pytest.mark.django_db
def test_pending_requests_are_listed_with_their_message(client, admin):
    _request()

    response = client.get(PAGE)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada Lovelace" in content
    assert "Working on follow-up." in content
    assert 'id="account-request-' in content


@pytest.mark.django_db
def test_approving_activates_the_account_in_the_chosen_groups(client, admin):
    account_request = _request()
    group = Group.objects.create(name="Gemini")

    response = _decide(client, account_request, action="approve", groups=[group.pk])

    user = User.objects.get(username="ada")
    assert user.is_active
    assert list(user.groups.all()) == [group]
    assert "Ada Lovelace can now sign in." in response.content.decode()


@pytest.mark.django_db
def test_declining_deletes_the_account(client, admin):
    account_request = _request()

    response = _decide(client, account_request, action="deny")

    assert not User.objects.filter(username="ada").exists()
    account_request.refresh_from_db()
    assert account_request.status == AccountRequest.STATUS_DENIED
    assert "Declined the request from Ada Lovelace." in response.content.decode()


@pytest.mark.django_db
def test_an_unknown_group_approves_nothing(client, admin):
    account_request = _request()

    response = _decide(client, account_request, action="approve", groups=[999])

    account_request.refresh_from_db()
    assert account_request.status == AccountRequest.STATUS_PENDING
    assert "One of those groups no longer exists." in response.content.decode()


@pytest.mark.django_db
def test_a_decided_request_is_not_decided_again(client, admin):
    account_request = _request()
    approve_account_request(account_request, admin)

    response = _decide(client, account_request, action="deny")

    assert User.objects.get(username="ada").is_active
    assert "already been decided" in response.content.decode()


@pytest.mark.django_db
def test_a_non_administrator_cannot_decide(client):
    account_request = _request()
    client.force_login(UserFactory())

    response = client.post(
        reverse("account-request-decide", args=[account_request.pk]),
        {"action": "approve"},
    )

    assert response.status_code == 403
    account_request.refresh_from_db()
    assert account_request.status == AccountRequest.STATUS_PENDING


@pytest.mark.django_db
def test_deciding_needs_a_post(client, admin):
    account_request = _request()

    response = client.get(reverse("account-request-decide", args=[account_request.pk]))

    assert response.status_code == 405


@pytest.mark.django_db
def test_a_request_whose_account_was_deleted_can_only_be_declined(client, admin):
    account_request = _request()
    account_request.user.delete()

    content = client.get(PAGE).content.decode()

    assert "Account deleted" in content
    assert 'value="approve"' not in content


@pytest.mark.django_db
def test_decisions_are_listed_with_who_made_them(client, admin):
    admin.first_name, admin.last_name = "Grace", "Hopper"
    admin.save()
    approve_account_request(_request(), admin)

    content = client.get(PAGE).content.decode()

    assert "Recent decisions" in content
    assert "Grace Hopper" in content


@pytest.mark.django_db
def test_a_link_to_a_decided_request_says_so(client, admin):
    account_request = _request()
    approve_account_request(account_request, admin)

    content = client.get(f"{PAGE}?request={account_request.pk}").content.decode()

    assert "The request from Ada Lovelace was" in content
    assert "approved" in content


@pytest.mark.django_db
def test_a_link_to_a_pending_request_shows_no_notice(client, admin):
    account_request = _request()

    content = client.get(f"{PAGE}?request={account_request.pk}").content.decode()

    assert "The request from" not in content


@pytest.mark.django_db
def test_the_user_list_marks_a_pending_account(client, admin):
    account_request = _request()

    content = client.get(reverse("user-list")).content.decode()

    assert f'{PAGE}#account-request-{account_request.pk}"' in content
    assert ">Pending</a>" in content


@pytest.mark.django_db
def test_only_administrators_get_the_menu_entry(client, admin):
    assert f'href="{PAGE}"' in client.get(reverse("home")).content.decode()

    client.force_login(UserFactory())
    assert f'href="{PAGE}"' not in client.get(reverse("home")).content.decode()
