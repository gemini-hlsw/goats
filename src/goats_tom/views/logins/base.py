__all__ = ["BaseLoginView"]
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView

from goats_tom.credentials import get_service_label
from goats_tom.service_checks import CheckResult


class BaseLoginView(LoginRequiredMixin, FormView):
    """View to handle Login form."""

    template_name = "auth/login_form.html"
    form_class = None
    service_name = None
    service_description = None
    login_client = None
    model_class = None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Reject attempts to manage another user's credentials.

        Parameters
        ----------
        request : `HttpRequest`
            The incoming request.

        Returns
        -------
        `HttpResponse`
            The response from the matching handler.

        Raises
        ------
        `PermissionDenied`
            If the requester is neither the user named in the URL nor a
            superuser.
        """
        # The target user comes from the URL, so it is not necessarily the requester.
        if not request.user.is_superuser and str(request.user.pk) != str(
            kwargs.get("pk")
        ):
            raise PermissionDenied("You may only manage your own service credentials.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        context["user"] = user
        context["service_name"] = self.service_name
        # The display label lives with the other service metadata.
        context["service_label"] = (
            get_service_label(self.request.resolver_match.url_name) or self.service_name
        )
        context["service_description"] = self.service_description

        return context

    def get_success_url(self) -> str:
        """Get the URL to redirect to on successful form submission.

        Returns
        -------
        `str`
            The URL to redirect to.

        """
        # Only an administrator can reach the user list, so everybody else
        # goes back to the settings page they came from.
        if self.request.user.is_superuser:
            return reverse_lazy("user-list")
        return reverse_lazy("user-update", kwargs={"pk": self.request.user.pk})

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

        try:
            result = self.verify_credentials(**data)
        except Exception:
            result = CheckResult(
                False,
                "The check could not be completed. Please try again later.",
                verified=False,
            )
        if not result.ok:
            if result.reachable and result.verified:
                reason = f"{self.service_name} rejected them."
            else:
                reason = result.message
            messages.error(
                self.request,
                f"Could not verify {self.service_name} credentials: {reason} "
                "Nothing was saved, and any credentials you already had "
                "are unchanged.",
            )
            # Re-render instead of form_invalid, which would add a second message.
            return self.render_to_response(self.get_context_data(form=form))

        if not result.verified:
            messages.success(
                self.request,
                f"{self.service_name} login information saved. It cannot be "
                "automatically verified at this time. If you experience issues "
                f"communicating with {self.service_name}, please double-check your "
                "credentials and try again.",
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

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Check the submitted credentials against the service; override in a
        subclass.

        Parameters
        ----------
        **kwargs : `Any`
            Arbitrary keyword arguments required for login.

        Returns
        -------
        `CheckResult`
            Whether the credentials were accepted and, if not, whether the
            service could be reached.
        """
        return CheckResult(True, "Not checked.", verified=False)
