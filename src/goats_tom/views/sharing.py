"""Sharing observation records and their data products with groups.

An observation and its files are private to the PI who triggered them: GOATS
assigns per-object permissions at creation, and nothing else grants them. That
is deliberate -- proprietary data should not follow a target around -- but it
leaves collaborators on a shared target able to see the target's name and
nothing else.

TOM Toolkit offers group selection only on its *creation* forms, and GOATS
creates both observation records and GOA data products programmatically, with
no form involved. So there was no way to share either after the fact. These
views are that missing half.

Notes
-----
Sharing is **per group**, matching how TOM shares targets and data products
everywhere else, so an object shared here behaves normally throughout the
rest of GOATS rather than only on the page that shared it.

Observations and their files are shared **separately and deliberately**.
Sharing an observation says "we triggered this"; sharing its data says "you
may have the data". A PI can coordinate without handing over proprietary
files, which is the distinction the whole per-object permission model exists
to preserve.

Only a user who may *change* an object can share it. View access is therefore
not transitive: a collaborator given sight of an observation cannot pass it
on to a third group.
"""

__all__ = ["share_observation_record", "share_data_products"]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from guardian.shortcuts import assign_perm, remove_perm
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

logger = logging.getLogger(__name__)

VIEW_OBSERVATION = "tom_observations.view_observationrecord"
CHANGE_OBSERVATION = "tom_observations.change_observationrecord"
VIEW_DATAPRODUCT = "tom_dataproducts.view_dataproduct"


def _requested_groups(request: HttpRequest) -> list[Group]:
    """Return the groups named in the request that the user belongs to.

    Notes
    -----
    Restricted to the requester's own groups. Without that check a user could
    post any group id and share proprietary data with a collaboration they
    have nothing to do with -- the select element lists only their groups,
    but the select element is not the security boundary.
    """
    ids = request.POST.getlist("groups")
    if not ids:
        return []
    return list(request.user.groups.filter(pk__in=ids))


def _may_share(user, obj, permission: str) -> bool:
    """Whether `user` may change `obj`, and so may share it.

    Notes
    -----
    Deliberately *change*, not view. Someone who has been given sight of an
    observation should not be able to widen that access further; sharing
    onward is the owner's decision to make.
    """
    return user.is_superuser or user.has_perm(permission, obj)


@login_required
@require_POST
def share_observation_record(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Grant or revoke group view access to one observation record.

    Parameters
    ----------
    request : `HttpRequest`
        POST carrying ``groups`` (group ids) and ``action``
        (``"share"`` or ``"unshare"``).
    pk : int
        Primary key of the `ObservationRecord`.

    Returns
    -------
    `HttpResponse`
        Redirect back to the observation's detail page.
    """
    record = get_object_or_404(ObservationRecord, pk=pk)
    if not _may_share(request.user, record, CHANGE_OBSERVATION):
        messages.error(
            request, "You do not have permission to share this observation."
        )
        return redirect("tom_observations:detail", pk=pk)

    groups = _requested_groups(request)
    if not groups:
        messages.warning(request, "Select at least one group.")
        return redirect("tom_observations:detail", pk=pk)

    unshare = request.POST.get("action") == "unshare"
    for group in groups:
        if unshare:
            remove_perm(VIEW_OBSERVATION, group, record)
        else:
            assign_perm(VIEW_OBSERVATION, group, record)

    names = ", ".join(g.name for g in groups)
    messages.success(
        request,
        f"Observation {'unshared from' if unshare else 'shared with'} {names}. "
        + (
            ""
            if unshare
            else "Its data products are still private -- share those separately."
        ),
    )
    logger.info(
        "Observation %s %s groups %s by %s.",
        record.pk,
        "unshared from" if unshare else "shared with",
        names,
        request.user.username,
    )
    return redirect("tom_observations:detail", pk=pk)


@login_required
@require_POST
def share_data_products(request: HttpRequest, pk: int) -> HttpResponse:
    """Grant or revoke group view access to data products.

    Parameters
    ----------
    request : `HttpRequest`
        POST carrying ``groups``, ``action``, and either ``products`` (data
        product ids) or ``all_products`` to mean every file on the
        observation.
    pk : int
        Primary key of the `ObservationRecord` the files belong to.

    Returns
    -------
    `HttpResponse`
        Redirect back to the observation's detail page.

    Notes
    -----
    Takes the observation's primary key rather than each file's, so
    permission is decided once against the observation the caller is looking
    at. Checking each file separately would let a caller mix ids from
    observations they do not own into a single request.

    A bulk option exists because a GOA download routinely produces dozens of
    files; sharing an observation's data one row at a time would be tedious
    enough that people would avoid it.
    """
    record = get_object_or_404(ObservationRecord, pk=pk)
    if not _may_share(request.user, record, CHANGE_OBSERVATION):
        messages.error(request, "You do not have permission to share this data.")
        return redirect("tom_observations:detail", pk=pk)

    groups = _requested_groups(request)
    if not groups:
        messages.warning(request, "Select at least one group.")
        return redirect("tom_observations:detail", pk=pk)

    products = DataProduct.objects.filter(observation_record=record)
    if not request.POST.get("all_products"):
        # Constrained to this observation's files, so an id from elsewhere
        # simply does not match.
        products = products.filter(pk__in=request.POST.getlist("products"))

    if not products.exists():
        messages.warning(request, "Select at least one data product.")
        return redirect("tom_observations:detail", pk=pk)

    unshare = request.POST.get("action") == "unshare"
    count = 0
    for product in products:
        for group in groups:
            if unshare:
                remove_perm(VIEW_DATAPRODUCT, group, product)
            else:
                assign_perm(VIEW_DATAPRODUCT, group, product)
        count += 1

    names = ", ".join(g.name for g in groups)
    messages.success(
        request,
        f"{count} data product{'' if count == 1 else 's'} "
        f"{'unshared from' if unshare else 'shared with'} {names}.",
    )
    logger.info(
        "%d data products of observation %s %s groups %s by %s.",
        count,
        record.pk,
        "unshared from" if unshare else "shared with",
        names,
        request.user.username,
    )
    return redirect("tom_observations:detail", pk=pk)
