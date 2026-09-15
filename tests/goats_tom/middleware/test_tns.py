


import pytest
from django.test.client import RequestFactory
from goats_tom.middleware.tns import (
    TNSCredentialsMiddleware,
    current_tns_creds,
)
from django.http import HttpRequest, HttpResponse
from goats_tom.tests.factories import TNSLoginFactory, UserFactory
from goats_tom import tns_membership as tm
from goats_tom.middleware.tns import SESSION_KEY
from goats_tom.models import TNSGroup


@pytest.mark.django_db
def test_middleware_sets_and_resets_context() -> None:
    """TNSCredentialsMiddleware sets ContextVar for /tns/ paths and clears it after."""

    login = TNSLoginFactory()

    def dummy_view(request: HttpRequest) -> HttpResponse:
        creds = current_tns_creds.get()
        assert creds is not None
        assert creds["bot_id"] == login.bot_id
        return HttpResponse("OK")

    middleware = TNSCredentialsMiddleware(dummy_view)

    factory = RequestFactory()
    request = factory.get("/tns/report/1")
    request.user = login.user

    assert current_tns_creds.get() is None

    response = middleware(request)
    assert response.status_code == 200

    # Ensure context is cleared after request
    assert current_tns_creds.get() is None


@pytest.mark.django_db
def test_middleware_skips_non_tns_paths() -> None:
    """TNSCredentialsMiddleware does not set context for non-/tns/ paths."""

    login = TNSLoginFactory()

    def dummy_view(request: HttpRequest) -> HttpResponse:
        assert current_tns_creds.get() is None
        return HttpResponse("OK")

    middleware = TNSCredentialsMiddleware(dummy_view)

    factory = RequestFactory()
    request = factory.get("/not-tns/")
    request.user = login.user

    assert current_tns_creds.get() is None

    response = middleware(request)
    assert response.status_code == 200
    assert current_tns_creds.get() is None


@pytest.mark.django_db
def test_middleware_uses_the_owners_bot_for_a_granted_group() -> None:
    """A member's request posts with the owner's key, scoped to one group.

    This is the whole of multi-user support in one assertion: the bot is
    the owner's, and `group_names` is narrowed to the single group that was
    granted -- `tom_tns` builds its reporting-group dropdown from that
    list, so anything wider would turn a one-group grant into access to
    every group the owner's bot can reach.
    """
    login = TNSLoginFactory(
        bot_id="42", bot_name="goatsbot", group_names=["Gemini", "Private"]
    )
    tm.sync_groups_for_login(login)
    shared = TNSGroup.objects.get(owner=login.user, name="Gemini")
    shared.allow_join_requests = True
    shared.recommended_authors = "A. Smith (NOIRLab)"
    shared.save()

    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=login.user
    )

    def dummy_view(request: HttpRequest) -> HttpResponse:
        creds = current_tns_creds.get()
        assert creds["bot_id"] == "42"
        assert creds["group_names"] == ["Gemini"]
        assert creds["recommended_authors"] == "A. Smith (NOIRLab)"
        return HttpResponse("OK")

    middleware = TNSCredentialsMiddleware(dummy_view)
    request = RequestFactory().get("/tns/1/")
    request.user = member
    request.session = {SESSION_KEY: f"group:{shared.pk}"}

    assert middleware(request).status_code == 200
    assert current_tns_creds.get() is None


@pytest.mark.django_db
def test_middleware_ignores_a_session_key_the_user_does_not_hold() -> None:
    """A forged session key falls back rather than being honoured.

    The key is user-controlled, so it is matched against what the member
    actually holds instead of trusted.
    """
    login = TNSLoginFactory(group_names=["Gemini", "Private"])
    tm.sync_groups_for_login(login)
    shared = TNSGroup.objects.get(owner=login.user, name="Gemini")
    shared.allow_join_requests = True
    shared.save()
    private = TNSGroup.objects.get(owner=login.user, name="Private")

    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=login.user
    )

    def dummy_view(request: HttpRequest) -> HttpResponse:
        assert current_tns_creds.get()["group_names"] == ["Gemini"]
        return HttpResponse("OK")

    middleware = TNSCredentialsMiddleware(dummy_view)
    request = RequestFactory().get("/tns/1/")
    request.user = member
    request.session = {SESSION_KEY: f"group:{private.pk}"}

    assert middleware(request).status_code == 200


@pytest.mark.django_db
def test_middleware_sets_nothing_for_a_user_with_no_access() -> None:
    """No credentials and no grants leaves the context untouched.

    `tom_tns` then falls back to its settings-based credentials, exactly as
    it did before sharing existed.
    """
    def dummy_view(request: HttpRequest) -> HttpResponse:
        assert current_tns_creds.get() is None
        return HttpResponse("OK")

    middleware = TNSCredentialsMiddleware(dummy_view)
    request = RequestFactory().get("/tns/1/")
    request.user = UserFactory()
    request.session = {}

    assert middleware(request).status_code == 200
