"""Tests for `goats_tom.accounts`."""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User

from goats_tom.accounts import (
    AccountRequestError,
    approve_account_request,
    create_account_request,
    deny_account_request,
)
from goats_tom.models import AccountRequest, Notification, OutgoingEmail
from goats_tom.tests.factories import UserFactory


@pytest.fixture
def admin():
    return UserFactory(is_superuser=True)


@pytest.fixture
def pending_request():
    """A pending request from Ada Lovelace."""
    user = User(
        username="ada",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.org",
    )
    user.set_password("an-analytical-engine")
    return create_account_request(user, message="Working on GOATS follow-up.")


@pytest.mark.django_db
def test_requesting_creates_an_inactive_account(pending_request):
    user = pending_request.user

    assert pending_request.status == AccountRequest.STATUS_PENDING
    assert not user.is_active
    assert user.check_password("an-analytical-engine")


@pytest.mark.django_db
def test_the_request_keeps_a_copy_of_who_asked(pending_request):
    assert pending_request.username == "ada"
    assert pending_request.full_name == "Ada Lovelace"
    assert pending_request.email == "ada@example.org"
    assert pending_request.message == "Working on GOATS follow-up."


@pytest.mark.django_db
def test_approving_activates_the_account_in_the_chosen_groups(admin, pending_request):
    chosen = Group.objects.create(name="Gemini")
    Group.objects.create(name="Other")

    approve_account_request(pending_request, admin, groups=[chosen])

    pending_request.refresh_from_db()
    user = pending_request.user
    assert pending_request.status == AccountRequest.STATUS_APPROVED
    assert pending_request.decided_by == admin
    assert user.is_active
    assert user.date_joined == pending_request.decided_at
    assert list(user.groups.all()) == [chosen]


@pytest.mark.django_db
def test_denying_deletes_the_account_and_keeps_the_record(admin, pending_request):
    deny_account_request(pending_request, admin)

    pending_request.refresh_from_db()
    assert pending_request.status == AccountRequest.STATUS_DENIED
    assert pending_request.decided_by == admin
    assert pending_request.user is None
    assert pending_request.username == "ada"
    assert not User.objects.filter(username="ada").exists()


@pytest.mark.django_db
def test_a_decided_request_cannot_be_decided_again(admin, pending_request):
    approve_account_request(pending_request, admin)

    with pytest.raises(AccountRequestError):
        deny_account_request(pending_request, admin)

    assert User.objects.get(username="ada").is_active


@pytest.mark.django_db
def test_two_admins_deciding_at_once_only_the_first_wins(admin, pending_request):
    # Both admins loaded the page while the request was pending.
    stale = AccountRequest.objects.get(pk=pending_request.pk)
    approve_account_request(pending_request, admin)

    with pytest.raises(AccountRequestError):
        deny_account_request(stale, UserFactory(is_superuser=True))

    pending_request.refresh_from_db()
    assert pending_request.status == AccountRequest.STATUS_APPROVED
    assert pending_request.decided_by == admin
    assert User.objects.get(username="ada").is_active


@pytest.mark.django_db
def test_a_request_whose_account_was_deleted_cannot_be_approved(admin, pending_request):
    pending_request.user.delete()
    pending_request.refresh_from_db()

    with pytest.raises(AccountRequestError):
        approve_account_request(pending_request, admin)

    pending_request.refresh_from_db()
    assert pending_request.status == AccountRequest.STATUS_PENDING


@pytest.mark.django_db
def test_requesting_tells_every_active_administrator():
    first, second = UserFactory(is_superuser=True), UserFactory(is_superuser=True)
    UserFactory(is_superuser=True, is_active=False)
    UserFactory()

    user = User(username="ada", first_name="Ada", last_name="Lovelace", email="a@x.org")
    account_request = create_account_request(user, affiliation="NOIRLab", message="Hi.")

    rows = Notification.objects.filter(kind="account.requested")
    assert {row.recipient for row in rows} == {first, second}
    row = rows.first()
    assert row.message == "Ada Lovelace requested a GOATS account."
    assert "Affiliation: NOIRLab" in row.detail
    assert "Hi." in row.detail
    assert row.url.endswith(f"#account-request-{account_request.pk}")
    assert row.actor == user


@pytest.mark.django_db
def test_a_failed_notification_leaves_no_account_behind(admin):
    user = User(username="ada", email="ada@example.org")

    with (
        patch("goats_tom.accounts.notify", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        create_account_request(user)

    assert not User.objects.filter(username="ada").exists()
    assert not AccountRequest.objects.exists()


@pytest.mark.django_db
def test_approving_clears_the_request_and_tells_the_applicant(admin, pending_request):
    approve_account_request(pending_request, admin)

    assert not Notification.objects.filter(
        kind="account.requested", read_at__isnull=True
    ).exists()
    approved = Notification.objects.get(kind="account.approved")
    assert approved.recipient == pending_request.user
    assert approved.title == "Welcome to GOATS"
    assert OutgoingEmail.objects.filter(
        to="ada@example.org", subject="[GOATS] Welcome to GOATS"
    ).exists()


@pytest.mark.django_db
def test_denying_clears_the_request_and_emails_the_applicant(admin, pending_request):
    deny_account_request(pending_request, admin)

    assert not Notification.objects.filter(
        kind="account.requested", read_at__isnull=True
    ).exists()
    email = OutgoingEmail.objects.get(to="ada@example.org")
    assert email.subject == "[GOATS] Your GOATS account request"
    assert "Ada Lovelace" in email.body
    assert '"ada"' in email.body
