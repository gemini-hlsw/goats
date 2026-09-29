"""POST endpoints for TNS group access decisions.

The four state changes, each reached by POST from either the TNS credential
page (`goats_tom.views.logins.tns.TNSLoginView`) or a target's TNS page.
There are no page views here: keeping the transitions as endpoints gives each
action one entry point whichever page the button was on.
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
from goats_tom.forms import TNSGroupSettingsFormSet, TNSJoinRequestForm
from goats_tom.models import TNSGroupJoinRequest, TNSGroupMembership
from goats_tom.templatetags.custom_filters import display_name
from goats_tom.tns_membership import (
    TNSJoinRequestError,
    approve_join_request,
    create_join_request,
    deny_join_request,
    owned_groups,
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
    Every action can be triggered from more than one page, so a fixed
    destination would bounce the user out of what they were doing.

    `Referer` is attacker-controllable and so validated rather than passed
    straight to `redirect`: otherwise an off-site referrer would forward the
    user to another host right after a successful POST, a redirect they have
    every reason to trust. `url_has_allowed_host_and_scheme` is the guard
    Django's own login view applies to `next`.
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
    Shared by both places a request can start. The form validates the group
    against `goats_tom.tns_membership.requestable_groups` for the acting
    user, so one they could not have been offered is rejected as invalid.
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

    # On commit, so an owner is never emailed about a request that rolled
    # back. Reaches an owner who is not signed in, unlike the toast.
    transaction.on_commit(lambda: notify_owner_of_tns_join_request(join_request))
    messages.success(
        request,
        "Access requested. The group owner will be notified and can approve "
        "or decline it.",
    )
    return _back(request)


@login_required
@require_POST
def tns_group_settings(request: HttpRequest) -> HttpResponse:
    """Save the acting user's whole list of TNS groups in one post.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object, carrying one formset row per group plus a
        blank one for adding.

    Returns
    -------
    `HttpResponse`
        Redirect back to the page the form was submitted from.

    Notes
    -----
    Adding, renaming, editing and removing are one operation because they are
    one table. Renaming in particular has to happen here rather than by
    retyping a list of names: a membership points at the row, so the people
    approved for a group survive the correction of a typo in it.

    Ownership rests on the queryset, not a separate check:
    `goats_tom.tns_membership.owned_groups` is the same call the page renders
    from, and `django.forms.models.BaseModelFormSet` resolves each row
    against it, so a forged primary key saves nothing. New rows have no owner
    of their own until it is set here, from the acting user.

    Removing a group cascades to its memberships and requests. The page says
    how many people that is before the box is ticked.
    """
    formset = TNSGroupSettingsFormSet(request.POST, queryset=owned_groups(request.user))

    if not formset.is_valid():
        # Named, not just refused: the redirect drops the bound formset, so
        # an error left on a row would never be seen.
        problems = [
            error
            for form in formset.forms
            for errors in form.errors.values()
            for error in errors
        ] or [formset.non_form_errors().as_text()]
        detail = " ".join(problem for problem in problems if problem)
        messages.error(
            request,
            f"Could not update your TNS groups: {detail or 'please check the names.'}",
        )
        return _back(request)

    with transaction.atomic():
        groups = formset.save(commit=False)
        removed = len(formset.deleted_objects)
        for group in formset.deleted_objects:
            group.delete()
        for group in groups:
            # Set rather than trusted: a new row arrives with no owner, and
            # an existing one came out of the acting user's own queryset.
            group.owner = request.user
            group.save()

    if removed:
        messages.success(
            request,
            f"Updated your TNS groups. Removed {removed}, "
            "along with any access granted to them.",
        )
    else:
        messages.success(request, "Updated your TNS groups.")

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
    Fetched scoped to the acting user's own groups, so guessing a primary key
    returns 404 rather than deciding another owner's request.
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
                f"{display_name(join_request.requester)} can now report under "
                f"'{join_request.tns_group.name}'.",
            )
        elif action == "deny":
            deny_join_request(join_request, decided_by=request.user)
            transaction.on_commit(
                lambda: notify_user_of_tns_join_decision(join_request)
            )
            messages.info(
                request,
                f"Declined the request from {display_name(join_request.requester)}.",
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
    Scoped by the lookup, as in `tns_decide_join_request`.
    """
    membership = get_object_or_404(
        TNSGroupMembership.objects.select_related("user", "tns_group"),
        pk=pk,
        tns_group__owner=request.user,
    )
    # Read before the row goes, and by the same rule the page follows: a
    # username is half of a login credential and names nobody to a colleague.
    who = display_name(membership.user)
    group_name = membership.tns_group.name
    revoke_membership(membership)
    messages.success(request, f"Removed {who}'s access to '{group_name}'.")
    return _back(request)
