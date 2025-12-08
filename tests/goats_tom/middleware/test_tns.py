


import pytest
from django.test.client import RequestFactory
from goats_tom.middleware.tns import (
    TNSCredentialsMiddleware,
    current_tns_creds,
)
from django.http import HttpRequest, HttpResponse
from goats_tom.tests.factories import TNSLoginFactory


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
