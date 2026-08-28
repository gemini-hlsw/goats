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

__all__ = ["grant_observation_permissions"]

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
