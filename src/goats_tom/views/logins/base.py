__all__ = ["BaseLoginView"]
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
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
        else:
            if self.service_name == "TNS":
                messages.success(
                    self.request,
                    "TNS login information saved. It cannot be automatically verified "
                    "at this time. If you experience issues communicating with TNS, "
                    "please double-check your credentials and try again.",
                )
            else:
                messages.success(
                    self.request,
                    f"{self.service_name} login information verified and saved "
                    "successfully.",
                )

        obj = form.save(commit=False)
        obj.user = user
        obj.save()

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
