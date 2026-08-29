"""What a given user may see, for every model that appears in a choice field.

`goats_tom.scoping` covers API viewsets -- the rows an endpoint *returns*.
This module covers the other half: the rows the interface *offers*, in
dropdowns, checkbox lists and filter sidebars.

They fail differently, and the second is easy to miss. A view can scope its
own queryset perfectly and still name every PI's saved selections in a
`<select>` beside it, because the list and the dropdown are built from
different querysets. That is exactly what happened with the observation list:
`ObservationListView.get_queryset` was scoped upstream, the add-to-group
action was scoped in GOATS, and the page still showed another PI's group
because the *filter form* was untouched.

Two separate reasons to scope these
-----------------------------------
**Disclosure.** A selection's name is information. ``sora_OG`` in a dropdown
tells the reader that a PI named sora exists and is working on something,
which on a proprietary-data instance is already more than they should have.

**Enforcement.** For a Django form the queryset *is* the validator: a
`ModelChoiceField` rejects any id outside its queryset. So narrowing a form's
queryset is not cosmetic -- it is what makes a hand-crafted POST fail. This
distinction matters when deciding what to do about a field: a hidden input is
still worth scoping, because nothing about being hidden stops someone posting
to it.

Scoping a rendered widget is never sufficient on its own. Views that act on
posted ids re-check permissions regardless, because a dropdown is a
suggestion and a query parameter is whatever the caller sent.

Target-only mode
----------------
Every helper returns everything when ``TARGET_PERMISSIONS_ONLY`` is True.
That is the desktop install, where per-object permissions are unused and
filtering here would hide a user's own work from them. This is what keeps the
hard invariant: with the setting at its default, nothing in this module
changes what anyone sees.
"""

__all__ = [
    "changeable_data_product_groups",
    "shareable_users",
    "changeable_observation_groups",
    "visible_data_product_groups",
    "visible_data_products",
    "visible_observation_groups",
    "visible_observation_records",
    "visible_target_lists",
    "visible_targets",
]

import logging

from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from tom_dataproducts.models import DataProduct, DataProductGroup
from tom_observations.models import ObservationGroup, ObservationRecord
from tom_targets.models import Target, TargetList

logger = logging.getLogger(__name__)

VIEW_DATAPRODUCT = "tom_dataproducts.view_dataproduct"
VIEW_DPGROUP = "tom_dataproducts.view_dataproductgroup"
CHANGE_DPGROUP = "tom_dataproducts.change_dataproductgroup"
CHANGE_OBSGROUP = "tom_observations.change_observationgroup"
VIEW_OBSERVATION = "tom_observations.view_observationrecord"
VIEW_OBSGROUP = "tom_observations.view_observationgroup"
VIEW_TARGETLIST = "tom_targets.view_targetlist"


def _resolve_user(user_or_request):
    """Return a user from either a user or a request.

    Notes
    -----
    Both are accepted because these helpers are called from two places with
    different conventions: `django_filters` hands a callable ``queryset``
    the request, while views have ``self.request.user`` already.
    """
    if user_or_request is None:
        return None
    return getattr(user_or_request, "user", user_or_request)


def _scoped(model, user_or_request, permission):
    """Objects of `model` that the user holds `permission` on.

    Notes
    -----
    An unauthenticated or missing user yields nothing rather than
    everything. The distinction matters: a `None` request reaching one of
    these helpers is a bug somewhere upstream, and the failure mode should
    be an empty dropdown somebody reports, not a full one nobody notices.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return model.objects.all()
    user = _resolve_user(user_or_request)
    if user is None or not getattr(user, "is_authenticated", False):
        return model.objects.none()
    return get_objects_for_user(user, permission)


def visible_target_lists(user_or_request):
    """Target groups (`TargetList`) the user may view.

    Notes
    -----
    Upstream offers these to anyone logged in -- see
    `tom_targets.filters.TargetFilterSet.get_target_list_queryset` and
    `tom_targets.views.TargetListView.get_context_data`, both of which
    check `is_authenticated` and then return everything. The
    add/remove-from-grouping endpoint does check `view_targetlist`, so the
    action was never open; only the names were.
    """
    return _scoped(TargetList, user_or_request, VIEW_TARGETLIST)


def visible_observation_groups(user_or_request):
    """Observation groups (`ObservationGroup`) the user may view."""
    return _scoped(ObservationGroup, user_or_request, VIEW_OBSGROUP)


def visible_data_product_groups(user_or_request):
    """Data product groups (`DataProductGroup`) the user may view."""
    return _scoped(DataProductGroup, user_or_request, VIEW_DPGROUP)


def changeable_data_product_groups(user_or_request):
    """Data product groups the user may modify.

    Notes
    -----
    Adding a file to a selection changes it, so a destination dropdown asks
    for change rather than view. Offering view-only selections would put
    entries in the list that the endpoint then refuses -- worse than not
    listing them, because it looks like a bug rather than a boundary.
    """
    return _scoped(DataProductGroup, user_or_request, CHANGE_DPGROUP)


def changeable_observation_groups(user_or_request):
    """Observation groups the user may modify, for the same reason."""
    return _scoped(ObservationGroup, user_or_request, CHANGE_OBSGROUP)


def visible_data_products(user_or_request):
    """Data products the user may view."""
    return _scoped(DataProduct, user_or_request, VIEW_DATAPRODUCT)


def visible_observation_records(user_or_request):
    """Observation records the user may view."""
    return _scoped(ObservationRecord, user_or_request, VIEW_OBSERVATION)


def visible_targets(user_or_request):
    """Targets the user may view.

    Notes
    -----
    Delegates to `tom_targets.permissions.targets_for_user`, which is what
    the target list and detail pages already use, so a dropdown built here
    agrees with the pages it links to.

    That function returns **everything for a superuser**, and this helper
    inherits it deliberately rather than quietly diverging. Whether an
    administrator should see every PI's proprietary targets is a real
    question, but it is TOM's behaviour across the whole application and
    changing it in one dropdown would only make the two disagree.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return Target.objects.all()
    user = _resolve_user(user_or_request)
    if user is None or not getattr(user, "is_authenticated", False):
        return Target.objects.none()

    from tom_targets.permissions import targets_for_user  # noqa: PLC0415

    return targets_for_user(user, Target.objects.all(), "view_target")


def shareable_users(user):
    """Every registered user `user` may share with.

    Notes
    -----
    All active accounts except the requester's own. Sharing with a named
    individual is narrower than sharing with a group, and there are cases
    the group model does not cover -- a visiting collaborator, an external
    referee, one colleague who needs a single file. Both grants are
    per-object view permissions, so an object shared either way behaves
    identically everywhere else in GOATS.

    This deliberately makes the instance's membership visible to anyone
    logged in. That is a real disclosure and a considered trade: on a
    collaborative instance the list of who has an account is far less
    sensitive than the proprietary data it guards, and a PI who cannot see
    a collaborator cannot share with them, which pushes people toward
    emailing files around instead -- a worse outcome than a visible user
    list. It is a policy choice rather than a technical constraint, and
    narrowing it later is a change to this function alone.

    Superusers are included. Today `targets_for_user` returns everything to
    an administrator anyway, so a grant to one changes nothing; but that is
    the open superuser question, and if admin access is ever narrowed, an
    administrator will need to be a legitimate share target like anyone
    else. Excluding them here would leave a second thing to remember.

    Inactive accounts are excluded: a disabled account should not be
    accumulating new access, and it cannot log in to use it.

    So is django-guardian's anonymous user. It is a genuine row in
    ``auth_user`` -- created by guardian's own migration so that
    permissions can be assigned to "not logged in" -- and without this
    exclusion it appears in the dropdown as a person named AnonymousUser.
    Sharing with it would grant read access to every unauthenticated
    visitor, which on a proprietary-data instance is the worst possible
    outcome of a mis-click. Read from settings rather than hardcoded,
    because guardian lets the name be configured.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    anonymous_name = getattr(settings, "ANONYMOUS_USER_NAME", "AnonymousUser")
    queryset = (
        get_user_model()
        .objects.filter(is_active=True)
        .exclude(pk=user.pk)
        .order_by("username")
    )
    if anonymous_name is not None:
        queryset = queryset.exclude(username=anonymous_name)
    return queryset
