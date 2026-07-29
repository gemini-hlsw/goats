__all__ = ["BaseLoginView"]
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView


class BaseLoginView(LoginRequiredMixin, FormView):
    """View to handle Login form."""

    template_name = "auth/login_form.html"
    form_class = None
    service_name = None
    service_description = None
    login_client = None
    model_class = None
    credentials_are_verifiable = True
    """Whether `perform_login_and_logout` actually checks credentials
    against the service (e.g. "is the endpoint reachable and the token
    valid"), rather than always returning `True` because no live check is
    available. Controls which success message is shown -- an honest
    "saved, but not verified" message when `False`, matching the
    subclass's own documented behavior, instead of falsely claiming
    "verified" for a credential that was never actually checked. Override
    to `False` in any subclass whose `perform_login_and_logout` doesn't
    perform a real check (see `TNSLoginView`, `AntaresKafkaLoginView`).
    """

    def dispatch(self, request, *args, **kwargs):
        """Reject attempts to view or edit another user's credentials.

        Credentials here are per-user secrets (GPP tokens, RSP access
        tokens, TNS keys, etc.). Without this check, the target user is
        taken straight from the URL (`kwargs["pk"]`) and
        `form_valid` writes to it via
        `model_class.objects.update_or_create(user=user, ...)` -- meaning
        any logged-in user could overwrite anyone else's stored
        credentials just by visiting `/users/<other_pk>/<service>/`.
        `LoginRequiredMixin` alone only checks *that* you're logged in,
        not *who* you are relative to the record being edited.

        Superusers are still allowed through, since the Credential
        Manager is an admin-facing tool and admins legitimately manage
        other users' entries. Mirrors the same guard TOM Toolkit already
        applies in its own `UserDeleteView`.
        """
        if (
            not request.user.is_superuser
            and str(request.user.pk) != str(self.kwargs.get("pk"))
        ):
            raise PermissionDenied(
                "You may only manage your own credentials."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        context["user"] = user
        context["service_name"] = self.service_name
        context["service_description"] = self.service_description

        return context

    def get_success_url(self) -> str:
        """Get the URL to redirect to on successful form submission.

        Returns
        -------
        `str`
            The URL to redirect to.

        """
        return reverse_lazy("user-list")

    def form_valid(self, form: Any) -> HttpResponse:
        """Handle valid form submission.

        Parameters
        ----------
        form : `Any`
            Valid form object.

        Returns
        -------
        `HttpResponse`
            HTTP response.
        """
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        data = form.cleaned_data

        # Test logging in and logging out.
        authenticated = self.perform_login_and_logout(**data)
        if not authenticated:
            messages.error(
                self.request,
                f"Failed to verify {self.service_name} credentials. Please try again.",
            )
        elif not self.credentials_are_verifiable:
            messages.success(
                self.request,
                f"{self.service_name} login information saved. It cannot be "
                f"automatically verified at this time. If you experience "
                f"issues communicating with {self.service_name}, please "
                f"double-check your credentials and try again.",
            )
        else:
            messages.success(
                self.request,
                f"{self.service_name} login information verified and saved "
                "successfully.",
            )

        # Update or create credentials.
        self.model_class.objects.update_or_create(
            user=user,
            defaults=data,
        )

        return super().form_valid(form)

    def form_invalid(self, form: Any) -> HttpResponse:
        """Handle invalid form submission.

        Parameters
        ----------
        form : `Any`
            Invalid form object.

        Returns
        -------
        `HttpResponse`
            HTTP response.
        """
        messages.error(
            self.request,
            f"Failed to save {self.service_name} login information. Please try again.",
        )
        return super().form_invalid(form)

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform the actual login or credential check and logout for the service,
        override in subclass.

        Parameters
        ----------
        **kwargs : `Any`
            Arbitrary keyword arguments required for login.

        Returns
        -------
        `bool`
            `True` if authentication succeeded, otherwise `False`.
        """
        return True
