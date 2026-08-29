"""Per-object permissions for objects GOATS creates on a user's behalf.

With ``TARGET_PERMISSIONS_ONLY = False`` -- the shared-server setting -- an
observation record carries its own permissions rather than inheriting whoever
can see its target. That is what lets one PI's observation stay private on a
target shared with collaborators.

It also means **an observation created without permissions is visible to
nobody**, including the person who created it. TOM Toolkit assigns them on
its *creation form*, from the groups the user selects, but every other route
into `ObservationRecord.objects.create` assigns none:

- `tom_observations.views.AddExistingObservationView` -- a bare create.
- `tom_observations.api_views.ObservationRecordViewSet` -- `perform_create`
  is `serializer.save()`, which is the path GOATS' Gemini triggering uses.

Those are silent failures: the record is written, a success message appears,
and the observation simply never shows up. Anything that creates an
observation outside the form must call `grant_observation_permissions`.
"""

__all__ = ["grant_dataproduct_permissions", "grant_observation_permissions"]

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

OBSERVATION_ACTIONS = ("view", "change", "delete")


def grant_observation_permissions(record, user) -> None:
    """Give `user` full per-object permissions on an observation record.

    Parameters
    ----------
    record : `tom_observations.models.ObservationRecord`
        The newly created record.
    user : `django.contrib.auth.models.User` or None
        The user who created it. `None` is tolerated and logged rather than
        raised on -- a record with no owner is a visibility problem, not a
        reason to fail a request that already succeeded at the observatory.

    Notes
    -----
    No-op when ``TARGET_PERMISSIONS_ONLY`` is True, where the target governs
    everything beneath it and these rows would be unused.

    Granted to the user alone, not to their groups. Sharing is theirs to
    decide afterwards from the observation page; doing it here would make
    the choice for them, and an observation shared by default is exactly
    what the per-object model exists to avoid.

    Change and delete come with view because the creator should be able to
    manage what they made. Recipients of a share get view only, which is
    what stops access being passed on further.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return
    if user is None or not getattr(user, "is_authenticated", False):
        logger.warning(
            "No user to grant permissions on observation %s; it will be "
            "invisible until permissions are assigned.",
            getattr(record, "observation_id", record),
        )
        return

    from guardian.shortcuts import assign_perm  # noqa: PLC0415

    try:
        for action in OBSERVATION_ACTIONS:
            assign_perm(f"tom_observations.{action}_observationrecord", user, record)
    except Exception:
        # Never fatal: the observation exists, and at the observatory it may
        # already be scheduled. Losing the record over a permissions failure
        # would be far worse than a visibility problem an administrator can
        # repair.
        logger.exception(
            "Could not assign permissions on observation %s to %s.",
            getattr(record, "observation_id", record),
            getattr(user, "username", None),
        )


DATAPRODUCT_ACTIONS = ("view", "change", "delete")


def grant_dataproduct_permissions(product, user, share_with_group=None) -> None:
    """Give `user` full per-object permissions on a newly created data product.

    Parameters
    ----------
    product : `tom_dataproducts.models.DataProduct`
        The newly created product.
    user : `django.contrib.auth.models.User` or None
        The user the creation is attributed to. `None` is tolerated and
        logged rather than raised on, for the same reason as
        `grant_observation_permissions`: the file exists and is on disk, and
        losing it over a permissions failure would be worse than a
        visibility problem an administrator can repair.
    share_with_group : `django.contrib.auth.models.Group`, optional
        A group to grant view alongside the user. Supplied only where the
        caller already knows the user's team from the save that created the
        product -- the dashboard's PI group, for instance. Left `None`
        everywhere else, because sharing is the PI's decision to make
        afterwards.

    Notes
    -----
    **Call this only when the product was created, never when one was
    updated.** Re-granting on update would silently hand ownership to
    whoever refreshed the file last, which on a shared locus means one PI
    taking a product another PI created. Callers gate on the ``created``
    flag from `get_or_create`.

    Grants are additive: guardian's `assign_perm` adds a row and removes
    none, so a product that is later shared keeps its existing holders.

    The group gets view only, matching the rule that recipients of a share
    cannot pass access on further.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return
    if user is None or not getattr(user, "is_authenticated", False):
        logger.warning(
            "No user to grant permissions on data product %s; it will be "
            "invisible until permissions are assigned.",
            getattr(product, "product_id", product),
        )
        return

    from guardian.shortcuts import assign_perm  # noqa: PLC0415

    try:
        for action in DATAPRODUCT_ACTIONS:
            assign_perm(f"tom_dataproducts.{action}_dataproduct", user, product)
        if share_with_group is not None:
            assign_perm("tom_dataproducts.view_dataproduct", share_with_group, product)
    except Exception:
        logger.exception(
            "Could not assign permissions on data product %s to %s.",
            getattr(product, "product_id", product),
            getattr(user, "username", None),
        )
