__all__ = ["BaseLoginView"]
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import (
    HttpResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView

from goats_tom.forms import BaseLoginForm


class BaseLoginView(LoginRequiredMixin, FormView):
    """View to handle Login form."""

    template_name = "auth/login_form.html"
    form_class = BaseLoginForm
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

    def form_valid(self, form: BaseLoginForm) -> HttpResponse:
        """Handle valid form submission.

        Parameters
        ----------
        form : `AstroDatalabForm`
            Valid form object.

        Returns
        -------
        `HttpResponse`
            HTTP response.
        """
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        # Test logging in to GOA.
        authenticated = self.perform_login_and_logout(username, password)
        if not authenticated:
            messages.error(
                self.request,
                f"Failed to verify {self.service_name} credentials. Please try again.",
            )
        else:
            messages.success(
                self.request,
                f"{self.service_name} login information verified and saved "
                "successfully.",
            )

        # Save or update credentials.
        if self.model_class is not None:
            self.model_class.objects.update_or_create(
                user=user,
                defaults={
                    "username": username,
                    "password": password,
                },
            )
        else:
            messages.warning(
                self.request,
                f"No model_class specified for {self.service_name}. Credentials not "
                "stored.",
            )

        return super().form_valid(form)

    def form_invalid(self, form: BaseLoginForm) -> HttpResponse:
        """Handle invalid form submission.

        Parameters
        ----------
        form : `BaseLoginForm`
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

    def perform_login_and_logout(self, username: str, password: str) -> bool:
        """Perform the actual login or credential check and logout for the service,
        override in subclass.

        Parameters
        ----------
        username : `str`
            The username to authenticate with.
        password : `str`
            The password to authenticate with.

        Returns
        -------
        `bool`
            `True` if authentication succeeded, otherwise `False`.
        """
        return True
