"""The sign-in page."""

__all__ = ["SignInView"]

from django.contrib.auth.views import LoginView

from goats_tom.forms import SignInForm


class SignInView(LoginView):
    """TOM's login page, telling applicants when their account awaits approval."""

    authentication_form = SignInForm
