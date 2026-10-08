import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.test.client import RequestFactory
from django.urls import reverse

from goats_tom.middleware import PermissionDeniedMiddleware
from goats_tom.tests.factories import UserFactory


def _run(user, response: HttpResponse, path: str = "/somewhere/") -> HttpResponse:
    request = RequestFactory().get(path)
    request.user = user
    return PermissionDeniedMiddleware(lambda _: response)(request)


def test_anonymous_403_redirects_to_login() -> None:
    response = _run(AnonymousUser(), HttpResponseForbidden(), "/somewhere/?a=1")

    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/somewhere/%3Fa%3D1"


def test_anonymous_login_redirect_is_kept() -> None:
    redirect = HttpResponseRedirect("/accounts/login/?next=/users/")

    assert _run(AnonymousUser(), redirect) is redirect


@pytest.mark.django_db
def test_authenticated_login_redirect_becomes_403() -> None:
    response = _run(
        UserFactory(), HttpResponseRedirect("/accounts/login/?next=/users/")
    )

    assert response.status_code == 403
    assert b"Access denied" in response.content


@pytest.mark.django_db
def test_authenticated_bare_403_renders_page() -> None:
    response = _run(UserFactory(), HttpResponseForbidden())

    assert response.status_code == 403
    assert b"Access denied" in response.content


@pytest.mark.django_db
def test_authenticated_403_with_body_is_kept() -> None:
    forbidden = HttpResponseForbidden("Not yours.")

    assert _run(UserFactory(), forbidden) is forbidden


@pytest.mark.django_db
def test_authenticated_other_redirect_is_kept() -> None:
    redirect = HttpResponseRedirect("/targets/")

    assert _run(UserFactory(), redirect) is redirect


@pytest.mark.django_db
def test_non_superuser_opening_user_list_gets_403(client) -> None:
    """Regression: a second user was sent back to the login page."""
    client.force_login(UserFactory())

    response = client.get(reverse("user-list"))

    assert response.status_code == 403
    assert response.wsgi_request.user.is_authenticated
