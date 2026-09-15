"""POST endpoints for TNS group access decisions.

There are no page views here any more. Everything an owner or a member
needs to see lives on the TNS credential page
(`goats_tom.views.logins.tns.TNSLoginView`), and requesting access happens
where the need arises -- on a target's TNS page, or in the small form on
that same credential page.

What is left is the four state changes, each reached by POST from one of
those two pages. Keeping them as endpoints rather than folding them into
the pages means the transition logic has exactly one caller-visible entry
point per action, whichever page the button was on.
"""

__all__ = [
    "tns_create_join_request",
    "tns_decide_join_request",
    "tns_revoke_membership",
    "tns_group_settings",
]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from goats_tom.emails import (
    notify_owner_of_tns_join_request,
    notify_user_of_tns_join_decision,
)
from goats_tom.forms import TNSGroupSettingsForm, TNSJoinRequestForm
from goats_tom.models import TNSGroup, TNSGroupJoinRequest, TNSGroupMembership
from goats_tom.tns_membership import (
    TNSJoinRequestError,
    approve_join_request,
    create_join_request,
    deny_join_request,
    revoke_membership,
)

logger = logging.getLogger(__name__)


def _back(request: HttpRequest) -> HttpResponse:
    """Redirect to the page the request came from.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        Redirect to the referring page, or to the user's own TNS credential
        page if there isn't a usable one.

    Notes
    -----
    Every action here can be triggered from more than one page -- the
    credential page and a target's TNS page -- so sending the user to a
    fixed destination would bounce them out of whatever they were doing.

    `Referer` is attacker-controllable, so it is validated rather than
    handed straight to `redirect`. Without the check, a link crafted with
    an off-site referrer would forward the user to another host immediately
    after a successful POST: a redirect they have every reason to trust,
    since they really had just submitted a GOATS form.
    `url_has_allowed_host_and_scheme` is the same guard Django's own login
    view applies to `next`.
    """
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect(reverse("user-tns-login", kwargs={"pk": request.user.pk}))


@login_required
@require_POST
def tns_create_join_request(request: HttpRequest) -> HttpResponse:
    """Ask to report under somebody else's TNS group.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads `tns_group` and `message`.

    Returns
    -------
    `HttpResponse`
        Redirect back to the page the request came from.

    Notes
    -----
    Shared by both places a request can start: the panel on a target's TNS
    page, shown when the user has no way to post, and the small form on
    their TNS credential page. The form validates the chosen group against
    `goats_tom.tns_membership.requestable_groups` for the acting user, so a
    submitted group the user could not have been offered is rejected as
    invalid rather than trusted.
    """
    form = TNSJoinRequestForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(
            request,
            "Could not request access: "
            f"{form.errors.as_text() or 'please choose a group.'}",
        )
        return _back(request)

    try:
        join_request = create_join_request(
            request.user,
            form.cleaned_data["tns_group"],
            message=form.cleaned_data["message"],
        )
    except TNSJoinRequestError as exc:
        messages.error(request, str(exc))
        return _back(request)

    # On commit, so an owner is never emailed about a request that then
    # rolled back. The in-app notification reaches only an owner who is
    # signed in; this is what reaches one who is observing.
    transaction.on_commit(lambda: notify_owner_of_tns_join_request(join_request))
    messages.success(
        request,
        "Access requested. The group owner will be notified and can approve "
        "or decline it.",
    )
    return _back(request)


@login_required
@require_POST
def tns_group_settings(request: HttpRequest, pk: int) -> HttpResponse:
    """Save the sharing toggle and co-author list for one group.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    pk : int
        Primary key of the group.

    Returns
    -------
    `HttpResponse`
        Redirect back to the page the form was submitted from.

    Notes
    -----
    Scoped to the requesting user's own groups by the lookup itself, so
    ownership is enforced by the query rather than by a separate check that
    could be forgotten.

    Turning `allow_join_requests` off does **not** revoke anyone already
    approved. The toggle governs whether *new* requests can be made;
    withdrawing access somebody is relying on is a separate, deliberate act
    (see `tns_revoke_membership`), not a side effect of closing the door to
    newcomers.
    """
    group = get_object_or_404(TNSGroup, pk=pk, owner=request.user)
    form = TNSGroupSettingsForm(request.POST, instance=group)

    if form.is_valid():
        form.save()
        messages.success(request, f"Updated settings for '{group.name}'.")
    else:
        messages.error(
            request,
            f"Could not update settings for '{group.name}': "
            f"{form.errors.as_text()}",
        )

    return _back(request)


@login_required
@require_POST
def tns_decide_join_request(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve or decline one request to report under a group.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads `action` (``"approve"`` or
        ``"deny"``).
    pk : int
        Primary key of the request to decide.

    Returns
    -------
    `HttpResponse`
        Redirect back to the page the decision was made on.

    Notes
    -----
    The request is fetched scoped to the acting user's own groups, so
    somebody cannot decide a request belonging to another owner's group by
    guessing a primary key -- the lookup returns 404 rather than the
    permission check being a separate step.
    """
    join_request = get_object_or_404(
        TNSGroupJoinRequest.objects.select_related("requester", "tns_group"),
        pk=pk,
        tns_group__owner=request.user,
    )

    action = request.POST.get("action")
    try:
        if action == "approve":
            approve_join_request(join_request, decided_by=request.user)
            transaction.on_commit(
                lambda: notify_user_of_tns_join_decision(join_request)
            )
            messages.success(
                request,
                f"{join_request.requester.username} can now report under "
                f"'{join_request.tns_group.name}'.",
            )
        elif action == "deny":
            deny_join_request(join_request, decided_by=request.user)
            transaction.on_commit(
                lambda: notify_user_of_tns_join_decision(join_request)
            )
            messages.info(
                request,
                f"Declined {join_request.requester.username}'s request.",
            )
        else:
            messages.error(request, "Unknown action.")
    except TNSJoinRequestError as exc:
        messages.error(request, str(exc))

    return _back(request)


@login_required
@require_POST
def tns_revoke_membership(request: HttpRequest, pk: int) -> HttpResponse:
    """Withdraw a member's permission to report under a group.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    pk : int
        Primary key of the membership to revoke.

    Returns
    -------
    `HttpResponse`
        Redirect back to the page it was revoked from.

    Notes
    -----
    Scoped to the owner's own groups for the same reason as
    `tns_decide_join_request`: the lookup itself enforces ownership.
    """
    membership = get_object_or_404(
        TNSGroupMembership.objects.select_related("user", "tns_group"),
        pk=pk,
        tns_group__owner=request.user,
    )
    username = membership.user.username
    group_name = membership.tns_group.name
    revoke_membership(membership)
    messages.success(request, f"Removed {username}'s access to '{group_name}'.")
    return _back(request)
