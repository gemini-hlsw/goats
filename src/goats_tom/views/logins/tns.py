__all__ = ["TNSLoginView"]

from typing import Any

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from goats_tom.forms import (
    TNSGroupSettingsForm,
    TNSJoinRequestForm,
    TNSLoginForm,
)
from goats_tom.models import (
    TNSGroup,
    TNSGroupJoinRequest,
    TNSGroupMembership,
    TNSLogin,
    TNSSubmissionRecord,
)
from goats_tom.tns_membership import sync_groups_for_login

from .base import BaseLoginView


class TNSLoginView(BaseLoginView):
    """The single page for TNS credentials, groups and access.

    Everything to do with TNS access lives here: the credentials, the
    per-group sharing settings, the requests waiting on the owner, who
    currently holds access, what the owner holds on other people's groups,
    and the log of submissions sent with these credentials.

    It was previously spread across this page plus two standalone pages at
    ``/tns/access/request/`` and ``/tns/access/manage/``, reached from the
    Brokers navbar menu. That was wrong twice over. TNS is not a broker, so
    the menu entry sat under a heading it had nothing to do with; and
    splitting "my groups' settings" from "requests to my groups" meant an
    owner had to visit two pages to answer one question -- who can post
    under my name, and who is asking to.

    The sharing settings are still not part of the credentials *form*, and
    cannot be. Groups are entered as free text in that form, so a group has
    no row to attach a toggle to until it has been saved once. Each section
    below posts separately.
    """

    service_name = "TNS"
    service_description = (
        "Provide the following details to be able to communicate with TNS."
    )
    model_class = TNSLogin
    form_class = TNSLoginForm
    credentials_are_verifiable = False
    template_name = "auth/tns_login_form.html"

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        # TODO: Figure out if there is a test or not.
        return True

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
        Every section other than the credentials form is gated on
        `is_own_page`. `BaseLoginView.dispatch` lets a superuser open
        another user's credential page, which is right for administering a
        stored secret and wrong for everything here: approving a request
        decides whose reports go out under *that user's* bot name, and
        revoking access withdraws something they granted. Those are the
        account holder's decisions, not an administrator's, so the sections
        are simply absent rather than shown read-only -- a disabled button
        invites someone to look for a way to enable it.
        """
        context = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        is_own_page = self.request.user.pk == user.pk
        context["is_own_page"] = is_own_page

        login = getattr(user, "tnslogin", None)
        names = (
            [name.strip() for name in (login.group_names or []) if name.strip()]
            if login is not None
            else []
        )
        # Only groups still named on the stored credentials. Rows for names
        # the user has since removed are kept in the database deliberately
        # (see `goats_tom.tns_membership.sync_groups_for_login`), but
        # offering their settings here would invite editing a group that is
        # no longer in play.
        groups = TNSGroup.objects.filter(owner=user, name__in=names).order_by(
            "name"
        )
        context["group_settings"] = [
            (group, TNSGroupSettingsForm(instance=group)) for group in groups
        ]

        if not is_own_page:
            return context

        context["pending_requests"] = (
            TNSGroupJoinRequest.objects.filter(
                tns_group__owner=user,
                status=TNSGroupJoinRequest.STATUS_PENDING,
            )
            .select_related("requester", "tns_group")
            .order_by("created_at")
        )
        context["members"] = (
            TNSGroupMembership.objects.filter(tns_group__owner=user)
            .select_related("user", "granted_by", "tns_group")
            .order_by("tns_group__name", "user__username")
        )
        # One row per group the user has asked for or holds, so "can I
        # report under X?" is answered in one table rather than by reading
        # two. Keyed by group: a request that was approved and the
        # membership it produced are the same row, not two.
        memberships = {
            membership.tns_group_id: membership
            for membership in TNSGroupMembership.objects.filter(user=user)
            .exclude(tns_group__owner=user)
            # `owner__tnslogin` is joined because the table shows the bot
            # name reports go out as; without it that column would fire a
            # query per row.
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
            # Newest first, and only the first kept: an earlier denial for a
            # group since re-requested and granted should not sit in the
            # table contradicting the current state.
            rows.setdefault(
                join_request.tns_group_id,
                {
                    "group": join_request.tns_group,
                    "requested_at": join_request.created_at,
                    "status": join_request.status,
                    "membership": memberships.get(join_request.tns_group_id),
                },
            )
        # Access granted without a request -- an owner adding someone
        # directly -- still belongs in the table, with no requested date.
        for group_id, membership in memberships.items():
            rows.setdefault(
                group_id,
                {
                    "group": membership.tns_group,
                    "requested_at": None,
                    "status": None,
                    "membership": membership,
                },
            )
        context["my_access"] = sorted(
            rows.values(), key=lambda row: row["group"].name
        )
        context["join_request_form"] = TNSJoinRequestForm(user=user)
        context["submissions"] = (
            TNSSubmissionRecord.objects.filter(owner=user)
            .select_related("submitted_by")
            .order_by("-created_at")[:25]
        )
        return context

    def form_valid(self, form: Any) -> HttpResponse:
        """Save the credentials, then create rows for any new group names.

        Notes
        -----
        Runs after `super()`, which is what writes the credentials -- the
        sync reads `group_names` back off the saved record, so it has to
        happen second or it would act on the previous values.
        """
        response = super().form_valid(form)
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        login = getattr(user, "tnslogin", None)
        if login is not None:
            sync_groups_for_login(login)
        return response
