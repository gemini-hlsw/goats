__all__ = ["TNSLoginView"]

from typing import Any

from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404

from goats_tom.forms import (
    TNSGroupSettingsFormSet,
    TNSJoinRequestForm,
    TNSLoginForm,
)
from goats_tom.models import (
    TNSGroupJoinRequest,
    TNSGroupMembership,
    TNSLogin,
    TNSSubmissionRecord,
)
from goats_tom.service_checks import CheckResult
from goats_tom.tns_membership import owned_groups

from .base import BaseLoginView


class TNSLoginView(BaseLoginView):
    """The single page for TNS credentials, groups and access.

    Everything to do with TNS access lives here: the credentials, the
    per-group sharing settings, the requests waiting on the owner, who holds
    access, what the owner holds elsewhere, and the submission log.

    The sharing settings cannot be part of the credentials *form*: groups are
    entered there as free text, so a group has no row to attach a toggle to
    until it has been saved once. Each section posts separately.
    """

    service_name = "TNS"
    service_description = (
        "Provide the following details to be able to communicate with TNS."
    )
    model_class = TNSLogin
    form_class = TNSLoginForm
    template_name = "auth/tns_login_form.html"

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Accept the credentials without checking them against TNS.

        Returns
        -------
        CheckResult
            Always a success marked unverified: no check is implemented, so
            the user is told the credentials were saved rather than verified.
        """
        # TODO: Figure out if there is a test or not.
        return CheckResult(True, "Not checked.", verified=False)

    def get_context_data(self, **kwargs):
        """Add every access-management section to the context.

        Returns
        -------
        dict
            The base context plus the sharing forms, the owner's request
            queue and members, the viewer's own access elsewhere, and the
            submission log.

        Notes
        -----
        Every section but the credentials form is gated on `is_own_page`.
        `BaseLoginView.dispatch` lets a superuser open another user's
        credential page, which is right for administering a stored secret and
        wrong here: approving a request decides whose reports go out under
        *that user's* bot name. The sections are absent rather than disabled,
        since a disabled button invites looking for a way to enable it.
        """
        context = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        is_own_page = self.request.user.pk == user.pk
        context["is_own_page"] = is_own_page

        # Everything about owning a bot is meaningless without one, so the
        # template hides those sections rather than showing three empty ones.
        context["has_credentials"] = hasattr(user, "tnslogin")
        # Counted so the row can say what removing the group would cost.
        groups = owned_groups(user).annotate(member_count=Count("memberships"))
        context["owned_groups"] = groups
        # One formset, so the whole table saves with one button.
        context["group_settings"] = (
            TNSGroupSettingsFormSet(queryset=groups) if is_own_page else None
        )

        if not is_own_page:
            return context

        context["access_rows"] = self._access_rows(user)
        # Keyed by group, so an approved request and the membership it
        # produced are one row rather than two.
        memberships = {
            membership.tns_group_id: membership
            for membership in TNSGroupMembership.objects.filter(user=user)
            .exclude(tns_group__owner=user)
            # `owner__tnslogin` joined: the table shows the bot name, which
            # would otherwise fire a query per row.
            .select_related(
                "tns_group", "tns_group__owner", "tns_group__owner__tnslogin"
            )
        }
        rows = {}
        for join_request in (
            TNSGroupJoinRequest.objects.filter(requester=user)
            .select_related(
                "tns_group", "tns_group__owner", "tns_group__owner__tnslogin"
            )
            .order_by("-created_at")
        ):
            # Newest kept, so an old denial cannot contradict a later grant.
            membership = memberships.get(join_request.tns_group_id)
            rows.setdefault(
                join_request.tns_group_id,
                {
                    "group": join_request.tns_group,
                    # Date of the status shown: granted, declined, removed
                    # or asked.
                    "when": (
                        membership.granted_at
                        if membership
                        else join_request.decided_at or join_request.created_at
                    ),
                    "status": join_request.status,
                    "membership": membership,
                },
            )
        # Access granted without a request still belongs in the table.
        for group_id, membership in memberships.items():
            rows.setdefault(
                group_id,
                {
                    "group": membership.tns_group,
                    "when": membership.granted_at,
                    "status": None,
                    "membership": membership,
                },
            )
        context["my_access"] = sorted(rows.values(), key=lambda row: row["group"].name)
        context["join_request_form"] = TNSJoinRequestForm(user=user)
        context["submissions"] = (
            TNSSubmissionRecord.objects.filter(owner=user)
            .select_related("submitted_by")
            .order_by("-created_at")[:25]
        )
        return context

    @staticmethod
    def _access_rows(user: User) -> list[dict[str, Any]]:
        """Who is asking for access to the user's groups, and who holds it.

        Parameters
        ----------
        user : `django.contrib.auth.models.User`
            The group owner.

        Returns
        -------
        list of dict
            One row per person and group, the ones awaiting a decision first.

        Notes
        -----
        Asking for access and holding it are two states of one relation, so
        they are one table. As two, "can Ada report under Gemini?" meant
        reading both of them, and the answer was whichever mentioned her.
        """
        rows: list[dict[str, Any]] = [
            {
                "user": join_request.requester,
                "group": join_request.tns_group,
                "status": "pending",
                "when": join_request.created_at,
                "message": join_request.message,
                "join_request": join_request,
                "membership": None,
            }
            for join_request in TNSGroupJoinRequest.objects.filter(
                tns_group__owner=user,
                status=TNSGroupJoinRequest.STATUS_PENDING,
            )
            .select_related("requester", "tns_group")
            .order_by("created_at")
        ]
        rows += [
            {
                "user": membership.user,
                "group": membership.tns_group,
                "status": "granted",
                "when": membership.granted_at,
                "message": "",
                "join_request": None,
                "membership": membership,
            }
            for membership in TNSGroupMembership.objects.filter(tns_group__owner=user)
            .select_related("user", "granted_by", "tns_group")
            .order_by("tns_group__name", "user__username")
        ]
        return rows
