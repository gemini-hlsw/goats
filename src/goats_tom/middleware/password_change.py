"""Middleware that holds a user on the new password page until they choose one."""

__all__ = ["CHANGE_REQUIRED", "PasswordChangeRequiredMiddleware"]

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

# Here, not with the views: this package is imported while the apps are loading.
CHANGE_REQUIRED = "goats_password_change_required"
"""Session key set while the signed-in user must choose a new password."""


class PasswordChangeRequiredMiddleware:
    """Redirect a user who signed in with a temporary password to choose a new one.

    Must come after `AuthenticationMiddleware`, which sets ``request.user``.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.session.get(CHANGE_REQUIRED)
            and request.user.is_authenticated
            and request.path_info not in (reverse("new_password"), reverse("logout"))
        ):
            return redirect("new_password")
        return self.get_response(request)
