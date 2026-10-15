"""Views where an administrator decides who gets an account."""

__all__ = [
    "AccountRequestListView",
    "AccountRequestDecideView",
    "PasswordResetDecideView",
]

from typing import Any

from django.contrib import messages
from django.contrib.auth.models import Group
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from tom_common.mixins import SuperuserRequiredMixin

from goats_tom.accounts import (
    AccountRequestError,
    approve_account_request,
    approve_password_reset,
    deny_account_request,
    deny_password_reset,
)
from goats_tom.forms import AccountApprovalForm
from goats_tom.models import AccountRequest, PasswordResetRequest

RECENT_DECISIONS = 20
"""How many decided requests the page lists."""


class AccountRequestListView(SuperuserRequiredMixin, TemplateView):
    """The pending account requests and password resets, then the latest decisions."""

    template_name = "auth/account_requests.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        requests = AccountRequest.objects.select_related("user__profile")
        context["pending_requests"] = requests.filter(
            status=AccountRequest.STATUS_PENDING
        )
        context["recent_decisions"] = (
            requests.exclude(status=AccountRequest.STATUS_PENDING)
            .select_related("decided_by")
            .order_by("-decided_at", "-pk")[:RECENT_DECISIONS]
        )
        context["groups"] = Group.objects.order_by("name")
        context["pending_password_resets"] = PasswordResetRequest.objects.filter(
            status=PasswordResetRequest.STATUS_PENDING
        ).select_related("user")
        context.update(self._linked_request())
        return context

    def _linked_request(self) -> dict[str, Any]:
        """The request a notification linked to, when it is no longer pending.

        Returns
        -------
        dict
            ``linked_request_closed`` and ``linked_request`` (it, if it still
            exists). Empty without a ``request`` query or while it is pending.
        """
        pk = self.request.GET.get("request", "")
        if not pk.isdigit():
            return {}
        account_request = (
            AccountRequest.objects.filter(pk=pk).select_related("decided_by").first()
        )
        if account_request and account_request.status == AccountRequest.STATUS_PENDING:
            # Still in the table, where the link's fragment scrolls to it.
            return {}
        return {"linked_request_closed": True, "linked_request": account_request}


class AccountRequestDecideView(SuperuserRequiredMixin, View):
    """Approve or deny one account request."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Apply the decision in ``action`` and go back to the requests.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request. Reads ``action`` (``"approve"`` or ``"deny"``) and,
            to approve, ``groups``.
        pk : int
            Primary key of the `AccountRequest`.

        Returns
        -------
        `HttpResponse`
            Redirect to the account requests page.
        """
        account_request = get_object_or_404(
            AccountRequest.objects.select_related("user"), pk=pk
        )
        name = account_request.full_name or account_request.email
        action = request.POST.get("action")
        try:
            if action == "approve":
                form = AccountApprovalForm(request.POST)
                if form.is_valid():
                    approve_account_request(
                        account_request, request.user, form.cleaned_data["groups"]
                    )
                    messages.success(request, f"{name} can now sign in.")
                else:
                    messages.error(
                        request, "One of those groups no longer exists. Try again."
                    )
            elif action == "deny":
                deny_account_request(account_request, request.user)
                messages.info(request, f"Declined the request from {name}.")
            else:
                messages.error(request, "Unknown action.")
        except AccountRequestError as exc:
            messages.error(request, str(exc))
        return redirect("account-requests")


@method_decorator(never_cache, name="dispatch")
class PasswordResetDecideView(SuperuserRequiredMixin, View):
    """Reset or deny one password reset request."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Apply the decision in ``action``.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request. Reads ``action`` (``"reset"`` or ``"deny"``).
        pk : int
            Primary key of the `PasswordResetRequest`.

        Returns
        -------
        `HttpResponse`
            After a reset, a page showing the temporary password once;
            otherwise a redirect to the account requests page.
        """
        reset_request = get_object_or_404(
            PasswordResetRequest.objects.select_related("user"), pk=pk
        )
        action = request.POST.get("action")
        try:
            if action == "reset":
                password = approve_password_reset(reset_request, request.user)
                # Rendered, not redirected: the password must not be stored anywhere.
                return render(
                    request,
                    "auth/password_reset_issued.html",
                    {"reset_request": reset_request, "password": password},
                )
            if action == "deny":
                deny_password_reset(reset_request, request.user)
                messages.info(request, "Declined the password reset.")
            else:
                messages.error(request, "Unknown action.")
        except AccountRequestError as exc:
            messages.error(request, str(exc))
        return redirect("account-requests")
