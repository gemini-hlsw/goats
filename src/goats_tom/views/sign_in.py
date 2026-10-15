"""The sign-in page."""

__all__ = ["SignInView"]

from typing import Any

from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from goats_tom.accounts import password_change_required
from goats_tom.forms import SignInForm
from goats_tom.middleware.password_change import CHANGE_REQUIRED
from goats_tom.outbox import email_enabled


class SignInView(LoginView):
    """TOM's login page, telling applicants when their account awaits approval."""

    authentication_form = SignInForm

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["password_reset_url"] = reverse(
            "password_reset" if email_enabled() else "password_reset_admin"
        )
        return context

    def form_valid(self, form: SignInForm) -> HttpResponse:
        response = super().form_valid(form)
        if password_change_required(form.get_user()):
            self.request.session[CHANGE_REQUIRED] = True
            return redirect("new_password")
        return response
