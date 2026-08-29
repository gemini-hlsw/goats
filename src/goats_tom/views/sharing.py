"""Sharing an observation record and its data with groups and people.

An observation and its files are private to the PI who triggered them: GOATS
assigns per-object permissions at creation, and nothing else grants them. That
is deliberate -- proprietary data should not follow a target around -- but it
leaves collaborators on a shared target able to see the target's name and
nothing else.

TOM Toolkit offers group selection only on its *creation* forms, and GOATS
creates both observation records and GOA data products programmatically, with
no form involved. So there was no way to share either after the fact. This
view is that missing half.

An observation and its data move together
-----------------------------------------
Sharing grants access to the record **and every data product on it**. There
is no per-file selection.

An earlier design shared the two separately, on the reasoning that a PI might
want to coordinate on an observation without releasing its data. In practice
that produced a per-file checkbox column, a bulk-selection row, a second
endpoint and a second set of permission checks -- a lot of moving parts for a
distinction nobody had asked to make. Worse, it was quietly broken: the
detail page listed every file on the observation regardless of permission,
so "share the record only" leaked the data anyway through the download links
in the table.

Collapsing it removes that whole class of bug. The unit of sharing is the
observation, which is also how people talk about it.

Two levels
----------
**Read-only** grants view on the record and view on its files: the
collaborator can see the observation and download the data.

**Full access** additionally grants change, so they can edit the observation,
run reductions and download new data through GOA.

**Neither grants delete.** Destruction stays with the owning PI. A
collaborator who deletes an observation's data by accident cannot undo it,
and the files may not be recoverable from GOA.

Only a user who may *change* an object can share it, so view access is not
transitive: a collaborator given sight of an observation cannot pass it on to
a third party.
"""

__all__ = ["share_observation_record"]

import logging

from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from guardian.shortcuts import assign_perm, remove_perm
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.visibility import shareable_users

logger = logging.getLogger(__name__)

VIEW_OBSERVATION = "tom_observations.view_observationrecord"
CHANGE_OBSERVATION = "tom_observations.change_observationrecord"
VIEW_DATAPRODUCT = "tom_dataproducts.view_dataproduct"
CHANGE_DATAPRODUCT = "tom_dataproducts.change_dataproduct"

#: Permissions granted at each level, by object.
#:
#: `delete` appears in neither: destruction stays with the owning PI.
LEVELS = {
    "read": {
        "observation": (VIEW_OBSERVATION,),
        "dataproduct": (VIEW_DATAPRODUCT,),
    },
    "full": {
        "observation": (VIEW_OBSERVATION, CHANGE_OBSERVATION),
        "dataproduct": (VIEW_DATAPRODUCT, CHANGE_DATAPRODUCT),
    },
}

#: Every permission this view is capable of granting.
#:
#: Used when removing access, so that revoking clears whatever was granted
#: rather than only the permissions of the level currently selected in the
#: form. Otherwise "remove access" on a record shared at full access would
#: silently leave change in place.
ALL_GRANTABLE = {
    "observation": (VIEW_OBSERVATION, CHANGE_OBSERVATION),
    "dataproduct": (VIEW_DATAPRODUCT, CHANGE_DATAPRODUCT),
}


def _requested_groups(request: HttpRequest) -> list[Group]:
    """Return the groups named in the request that the user belongs to.

    Notes
    -----
    Restricted to the requester's own groups. Without that check a user could
    post any group id and share proprietary data with a collaboration they
    have nothing to do with -- the select element lists only their groups,
    but the select element is not the security boundary.

    Unlike the people list, which is every registered user, group sharing
    stays restricted: a group grant reaches people the sharer may not know
    and cannot see.
    """
    ids = request.POST.getlist("groups")
    if not ids:
        return []
    return list(request.user.groups.filter(pk__in=ids))


def _requested_users(request: HttpRequest) -> list:
    """Return the users named in the request the requester may share with.

    Notes
    -----
    Filtered through `shareable_users` for the same reason
    `_requested_groups` filters through the requester's own groups: the
    posted ids are whatever the caller sent, and the rendered options are
    not a boundary. That helper also excludes guardian's anonymous user,
    which would otherwise grant access to every unauthenticated visitor.
    """
    ids = request.POST.getlist("users")
    if not ids:
        return []
    return list(shareable_users(request.user).filter(pk__in=ids))


def _requested_principals(request: HttpRequest) -> list:
    """Every group and user this request is asking to share with.

    Notes
    -----
    Returned as one list because guardian's `assign_perm` and `remove_perm`
    accept a user or a group interchangeably, so the two need no separate
    handling once each has been validated.
    """
    return _requested_groups(request) + _requested_users(request)


def _principal_names(principals) -> str:
    """Human-readable list of principals, for messages and the audit log."""
    return ", ".join(
        getattr(p, "name", None) or getattr(p, "username", str(p)) for p in principals
    )


def _may_share(user, record) -> bool:
    """Whether `user` may change `record`, and so may share it.

    Notes
    -----
    Deliberately *change*, not view. Someone who has been given sight of an
    observation should not be able to widen that access further; sharing
    onward is the owner's decision to make.
    """
    return user.is_superuser or user.has_perm(CHANGE_OBSERVATION, record)


@login_required
@require_POST
def share_observation_record(request: HttpRequest, pk: int) -> HttpResponse:
    """Grant or revoke access to an observation record and all its data.

    Parameters
    ----------
    request : `HttpRequest`
        POST carrying ``groups`` (group ids) and/or ``users`` (user ids),
        ``level`` (``"read"`` or ``"full"``), and ``action``
        (``"share"`` or ``"unshare"``). Either principal list may be empty
        as long as one is not.
    pk : int
        Primary key of the `ObservationRecord`.

    Returns
    -------
    `HttpResponse`
        Redirect back to the observation's detail page.

    Notes
    -----
    The record and its data products are granted together, in one
    transaction. A partial grant is the failure mode worth avoiding here:
    an observation visible with its files missing looks like data loss to
    the recipient, and files visible without their observation are
    unreachable through the interface.

    Files are resolved from the record rather than from the request, so
    there is nothing for a caller to tamper with -- ids posted for products
    belonging to another observation have nowhere to go.
    """
    record = get_object_or_404(ObservationRecord, pk=pk)
    if not _may_share(request.user, record):
        messages.error(request, "You do not have permission to share this observation.")
        return redirect("tom_observations:detail", pk=pk)

    principals = _requested_principals(request)
    if not principals:
        messages.warning(request, "Select at least one group or person.")
        return redirect("tom_observations:detail", pk=pk)

    unshare = request.POST.get("action") == "unshare"
    level = request.POST.get("level", "read")
    if level not in LEVELS:
        level = "read"

    products = list(DataProduct.objects.filter(observation_record=record))

    if unshare:
        # Everything this view can grant, not merely the level currently
        # selected: otherwise removing access from a record shared at full
        # access would leave change behind.
        observation_perms = ALL_GRANTABLE["observation"]
        product_perms = ALL_GRANTABLE["dataproduct"]
    else:
        observation_perms = LEVELS[level]["observation"]
        product_perms = LEVELS[level]["dataproduct"]

    with transaction.atomic():
        for principal in principals:
            for permission in observation_perms:
                if unshare:
                    remove_perm(permission, principal, record)
                else:
                    assign_perm(permission, principal, record)
            for product in products:
                for permission in product_perms:
                    if unshare:
                        remove_perm(permission, principal, product)
                    else:
                        assign_perm(permission, principal, product)

    names = _principal_names(principals)
    count = len(products)
    files = f"{count} file{'' if count == 1 else 's'}"
    if unshare:
        messages.success(request, f"Access to this observation removed from {names}.")
    else:
        described = "full access to" if level == "full" else "read-only access to"
        messages.success(
            request,
            f"Shared {described} this observation and its {files} with {names}."
            + (
                ""
                if level == "read"
                else " They can edit the observation and download new data."
            ),
        )

    logger.info(
        "Observation %s (%d data products) %s %s at level %s by %s.",
        record.pk,
        count,
        "unshared from" if unshare else "shared with",
        names,
        "revoked" if unshare else level,
        request.user.username,
    )
    return redirect("tom_observations:detail", pk=pk)
