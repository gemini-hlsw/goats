"""Views for requesting and granting access to ANTARES dashboards."""

__all__ = [
    "antares_request_access",
    "antares_manage_access",
    "antares_decide_join_request",
    "antares_revoke_membership",
]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from goats_tom.antares_membership import (
    JoinRequestError,
    approve_join_request,
    create_join_request,
    deny_join_request,
    revoke_membership,
)
from goats_tom.forms import AntaresJoinRequestForm
from goats_tom.models import (
    AntaresDashboardMembership,
    AntaresGroupJoinRequest,
    AntaresPIGroup,
)

logger = logging.getLogger(__name__)


def _pi_group_or_404(user) -> AntaresPIGroup:
    """Return `user`'s own PI group, or raise `Http404`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The requesting user.

    Returns
    -------
    `goats_tom.models.AntaresPIGroup`
        The user's group.

    Raises
    ------
    `Http404`
        If the user has no PI group -- i.e. they have never stored ANTARES
        Kafka credentials, so they are not a PI and have no access to
        manage. A 404 rather than a redirect, since there is genuinely no
        such page for this user.
    """
    pi_group = AntaresPIGroup.objects.filter(pi=user).first()
    if pi_group is None:
        raise Http404("You do not have an ANTARES PI group.")
    return pi_group


@login_required
def antares_request_access(request: HttpRequest) -> HttpResponse:
    """Show and handle the "request access to a PI's dashboard" form.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered form, or a redirect back to it after submission.

    Notes
    -----
    Also lists the user's own past requests, so a pending request is visible
    rather than appearing to have vanished -- without that, a user with a
    request already in flight would see it filtered out of the group
    dropdown (see `goats_tom.antares_membership.requestable_pi_groups`) with
    no indication of why.
    """
    if request.method == "POST":
        form = AntaresJoinRequestForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                create_join_request(
                    request.user,
                    form.cleaned_data["pi_group"],
                    request_save_targets=form.cleaned_data[
                        "request_save_targets"
                    ],
                    message=form.cleaned_data["message"],
                )
            except JoinRequestError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Access requested. The PI will be notified and can "
                    "approve or decline it.",
                )
                return redirect("antares-request-access")
    else:
        form = AntaresJoinRequestForm(user=request.user)

    my_requests = (
        AntaresGroupJoinRequest.objects.filter(requester=request.user)
        .select_related("pi_group__group", "pi_group__pi")
        .order_by("-created_at")
    )
    my_memberships = (
        AntaresDashboardMembership.objects.filter(user=request.user)
        .select_related("pi_group__group", "pi_group__pi")
        .order_by("pi_group__group__name")
    )

    return render(
        request,
        "antares_request_access.html",
        {
            "form": form,
            "my_requests": my_requests,
            "my_memberships": my_memberships,
            # Lets the template distinguish "nothing exists yet" from "you
            # have already asked for everything". Offering one message for
            # both reads as an error immediately after a successful request:
            # the page says access was requested, then says there is nothing
            # to request.
            "any_pi_groups_exist": AntaresPIGroup.objects.exists(),
        },
    )


@login_required
def antares_manage_access(request: HttpRequest) -> HttpResponse:
    """Show a PI's pending join requests and current members.

    This page, rendered from the database, is the authoritative view of
    pending requests -- not the real-time notification that accompanies a
    new one. A notification only reaches connected sessions, so a PI who was
    offline would otherwise never learn of a request.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered management page.

    """
    pi_group = _pi_group_or_404(request.user)

    pending = (
        pi_group.join_requests.filter(
            status=AntaresGroupJoinRequest.STATUS_PENDING
        )
        .select_related("requester")
        .order_by("created_at")
    )
    decided = (
        pi_group.join_requests.exclude(
            status=AntaresGroupJoinRequest.STATUS_PENDING
        )
        .select_related("requester", "decided_by")
        .order_by("-decided_at")[:20]
    )
    members = (
        pi_group.memberships.select_related("user", "granted_by")
        .order_by("user__username")
    )

    return render(
        request,
        "antares_manage_access.html",
        {
            "pi_group": pi_group,
            "pending_requests": pending,
            "decided_requests": decided,
            "members": members,
        },
    )


@login_required
@require_POST
def antares_decide_join_request(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Approve or deny one join request.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads `action` (``"approve"`` or
        ``"deny"``) and, when approving, the `grant_view` and `grant_save`
        checkboxes.
    pk : int
        Primary key of the request to decide.

    Returns
    -------
    `HttpResponse`
        Redirect back to the management page.

    Notes
    -----
    The request is fetched scoped to the PI's *own* group, so a PI cannot
    decide a request belonging to someone else's group by guessing a primary
    key -- the lookup returns 404 rather than the permission check being a
    separate step that could be forgotten.
    """
    pi_group = _pi_group_or_404(request.user)
    join_request = get_object_or_404(
        AntaresGroupJoinRequest.objects.select_related("requester"),
        pk=pk,
        pi_group=pi_group,
    )

    action = request.POST.get("action")
    try:
        if action == "approve":
            # Default to granting view but not save: saving creates targets
            # and fetches light curves, so it stays opt-in even at approval
            # time rather than being inherited from what was requested.
            approve_join_request(
                join_request,
                decided_by=request.user,
                grant_view=bool(request.POST.get("grant_view", True)),
                grant_save=bool(request.POST.get("grant_save")),
            )
            messages.success(
                request,
                f"Approved access for {join_request.requester.username}.",
            )
        elif action == "deny":
            deny_join_request(join_request, decided_by=request.user)
            messages.info(
                request,
                f"Declined access for {join_request.requester.username}.",
            )
        else:
            messages.error(request, "Unknown action.")
    except JoinRequestError as exc:
        messages.error(request, str(exc))

    return redirect("antares-manage-access")


@login_required
@require_POST
def antares_revoke_membership(request: HttpRequest, pk: int) -> HttpResponse:
    """Remove a member's access to the PI's dashboard.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    pk : int
        Primary key of the membership to revoke.

    Returns
    -------
    `HttpResponse`
        Redirect back to the management page.

    Notes
    -----
    Scoped to the PI's own group for the same reason as
    `antares_decide_join_request`: the lookup itself enforces ownership.
    """
    pi_group = _pi_group_or_404(request.user)
    membership = get_object_or_404(
        AntaresDashboardMembership.objects.select_related("user"),
        pk=pk,
        pi_group=pi_group,
    )
    username = membership.user.username
    revoke_membership(membership)
    messages.success(request, f"Removed {username}'s access.")
    return redirect("antares-manage-access")
