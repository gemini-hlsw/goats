"""Tests for the one way to read a user's stored credentials."""

import pytest
from django.contrib.auth.models import AnonymousUser

from goats_tom.context.user_context import user_id_context
from goats_tom.credentials import (
    MissingCredentialsError,
    get_credentials,
    require_credentials,
)
from goats_tom.models import GOALogin, GPPLogin
from goats_tom.tests.factories import GOALoginFactory, GPPLoginFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_a_user_that_is_handed_over_is_used() -> None:
    """Given a user, their own credentials come back."""
    login = GPPLoginFactory(token="abc123")

    assert get_credentials(GPPLogin, user=login.user) == login


def test_a_user_without_credentials_gets_none() -> None:
    """A user who stored nothing for a service is not an error."""
    user = UserFactory()

    assert get_credentials(GPPLogin, user=user) is None


def test_an_anonymous_user_gets_none() -> None:
    """Nobody has no credentials."""
    assert get_credentials(GPPLogin, user=AnonymousUser()) is None


def test_the_user_is_taken_from_the_context() -> None:
    """With no user handed over, the one the context names is used.

    This is the case background tasks are in: there is no request to ask.
    """
    login = GPPLoginFactory(token="abc123")

    with user_id_context(login.user.pk):
        assert get_credentials(GPPLogin) == login


def test_no_context_and_no_user_gets_none() -> None:
    """Outside a request and a task there is nobody to read credentials for."""
    GPPLoginFactory(token="abc123")

    assert get_credentials(GPPLogin) is None


def test_the_user_handed_over_wins_over_the_context() -> None:
    """An explicit user is the answer, whatever the context says."""
    asked_for = GPPLoginFactory(token="asked-for")
    in_context = GPPLoginFactory(token="in-context")

    with user_id_context(in_context.user.pk):
        assert get_credentials(GPPLogin, user=asked_for.user) == asked_for


def test_each_service_is_read_on_its_own() -> None:
    """Credentials for one service say nothing about another's."""
    user = UserFactory()
    goa = GOALoginFactory(user=user)

    assert get_credentials(GOALogin, user=user) == goa
    assert get_credentials(GPPLogin, user=user) is None


def test_requiring_credentials_that_are_there_returns_them() -> None:
    """The strict reader hands back what the plain one would."""
    login = GPPLoginFactory(token="abc123")

    assert require_credentials(GPPLogin, user=login.user) == login


def test_requiring_credentials_that_are_missing_raises() -> None:
    """Callers that cannot go on without credentials get told which are missing."""
    user = UserFactory()

    with pytest.raises(MissingCredentialsError, match="No GPPLogin credentials"):
        require_credentials(GPPLogin, user=user)
