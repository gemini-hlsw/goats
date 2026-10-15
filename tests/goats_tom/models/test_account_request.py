import pytest

from goats_tom.models import AccountRequest
from goats_tom.tests.factories import UserFactory


@pytest.mark.django_db()
def test_a_new_request_is_pending():
    user = UserFactory(is_active=False)
    account_request = AccountRequest.objects.create(
        user=user, username=user.username, email="ada@example.org"
    )

    assert account_request.status == AccountRequest.STATUS_PENDING
    assert account_request.decided_at is None
    assert user.account_request == account_request


@pytest.mark.django_db()
def test_deleting_the_account_keeps_the_request():
    user = UserFactory(is_active=False)
    account_request = AccountRequest.objects.create(
        user=user, username=user.username, email="ada@example.org"
    )

    user.delete()
    account_request.refresh_from_db()

    assert account_request.user is None
    assert account_request.username == user.username
    assert account_request.email == "ada@example.org"
