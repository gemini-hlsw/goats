"""Middleware that never sends a signed-in user back to the login page."""

__all__ = ["PermissionDeniedMiddleware"]

from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.views.defaults import permission_denied


def _is_login_redirect(response: HttpResponse) -> bool:
    """Whether `response` redirects to the login page.

    Parameters
    ----------
    response : `HttpResponse`
        The response produced by the view.

    Returns
    -------
    bool
        `True` for a redirect whose target path is ``LOGIN_URL``.
    """
    if response.status_code not in (301, 302):
        return False
    location = urlparse(response.get("Location", "")).path
    return location == resolve_url(settings.LOGIN_URL)


class PermissionDeniedMiddleware:
    """Replace `tom_common.middleware.Raise403Middleware`.

    Anonymous users refused with a 403 are redirected to the login page, as
    upstream does. Signed-in users get the 403 page instead, both when a view
    refuses them and when it redirects them to the login page, which is what
    TOM's `SuperuserRequiredMixin` does via `user_passes_test`.

    Must sit where `Raise403Middleware` sat, outside `AuthStrategyMiddleware`,
    so it sees the 403 that the ``LOCKED`` strategy returns to anonymous users.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            if response.status_code == 403:
                # Deferred: `django.contrib.auth.views` needs the app registry,
                # and this package is imported while the apps are loading.
                from django.contrib.auth.views import redirect_to_login  # noqa: PLC0415

                return redirect_to_login(request.get_full_path())
            return response

        # A 403 that already has a body (e.g. the rendered `403.html`) is kept.
        bare_403 = (
            response.status_code == 403
            and not response.streaming
            and not response.content
        )
        if bare_403 or _is_login_redirect(response):
            return permission_denied(request, PermissionDenied())
        return response
