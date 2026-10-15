"""Resetting a forgotten password: by email, or through an administrator."""

__all__ = [
    "NewPasswordView",
    "PasswordResetByAdminDoneView",
    "PasswordResetByAdminView",
    "PasswordResetRequestView",
]

from typing import Any

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from goats_tom.accounts import complete_password_change, request_password_reset
from goats_tom.forms import (
    NewPasswordForm,
    PasswordResetRequestForm,
    PasswordResetUsernameForm,
)
from goats_tom.middleware.password_change import CHANGE_REQUIRED
from goats_tom.outbox import email_enabled


class PasswordResetRequestView(PasswordResetView):
    """Django's page to request a reset link, available only when email is on."""

    form_class = PasswordResetRequestForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not email_enabled():
            raise Http404("This GOATS instance does not send email.")
        return super().dispatch(request, *args, **kwargs)


class _EmailOffMixin:
    """Answer 404 when email is on, where the reset link goes by email."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if email_enabled():
            raise Http404("Password reset goes by email on this GOATS instance.")
        return super().dispatch(request, *args, **kwargs)


class PasswordResetByAdminView(_EmailOffMixin, FormView):
    """Ask the administrators to reset a password."""

    form_class = PasswordResetUsernameForm
    template_name = "registration/password_reset_admin.html"

    def form_valid(self, form: PasswordResetUsernameForm) -> HttpResponse:
        # The same answer whether or not the account exists.
        request_password_reset(form.cleaned_data["username"])
        return redirect("password_reset_admin_done")


class PasswordResetByAdminDoneView(_EmailOffMixin, TemplateView):
    """Tell the user an administrator will give them a temporary password."""

    template_name = "registration/password_reset_admin_done.html"


class NewPasswordView(LoginRequiredMixin, FormView):
    """Where a user signed in with a temporary password chooses a new one."""

    form_class = NewPasswordForm
    template_name = "registration/new_password.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: NewPasswordForm) -> HttpResponse:
        user = form.save()
        complete_password_change(user)
        # Keeps the user signed in under the new password.
        update_session_auth_hash(self.request, user)
        self.request.session.pop(CHANGE_REQUIRED, None)
        messages.success(self.request, "Your new password is set.")
        return redirect("home")
