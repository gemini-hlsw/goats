"""Shared logic for saving an ANTARES locus as a GOATS `Target`.

Used by:
- `goats_tom.tasks.ingest_antares_stream`, when the "Automatically save
  all ingested loci as targets" option is enabled on the subscription.
- `goats_tom.views.antares_locus_dashboard.antares_locus_save_targets`,
  the dashboard's "Save selected" button.

The antares2goats browser extension (see
`goats_tom.api_views.antares2goats.Antares2GoatsViewSet`) saves targets via
a separate path directly from the ANTARES portal, but produces targets in
the same shape (`Target.name == locus_id` via `ANTARESBroker.to_target`,
plus light curve data via `process_lightcurve_data`/`create_lightcurve_dp`/
`create_reduced_datums`) -- `save_locus_as_target` here follows the exact
same sequence, so targets saved through GOATS' own two paths match
extension-saved ones, and `locus_is_saved_as_target` correctly recognizes
extension-saved targets too.

A locus is one real object in the sky, so GOATS keeps exactly one `Target`
for it and *shares* that target between teams rather than duplicating it.
Duplication was considered and rejected: `Target.name` is unique at the
database level and TOM additionally rejects fuzzy and alias collisions
(`TargetMatchManager.is_unique`), so allowing two rows for one locus would
mean mangling names and disabling TOM's duplicate detection for all of
GOATS -- weakening a protection that has nothing to do with ANTARES in
order to solve a permissions problem. Instead, saving a locus somebody else
already saved is additive: the second team is granted access to the
existing target (see `share_target_with_group`).
"""

__all__ = [
    "is_shared_target",
    "locus_is_saved_as_target",
    "save_locus_as_target",
    "share_target_with_group",
    "target_locus_names",
    "target_saver_usernames",
    "SaveLocusError",
    "SharedTargetDeletionError",
]

import logging

from guardian.shortcuts import assign_perm
from tom_alerts.alerts import get_service_class as tom_alerts_get_service_class
from tom_targets.models import Target

from goats_tom.models import AntaresTargetSave

logger = logging.getLogger(__name__)


class SaveLocusError(Exception):
    """Raised when a locus cannot be fetched or saved as a target."""


class SharedTargetDeletionError(Exception):
    """Raised when a target held by more than one team is deleted."""


def target_locus_names(target) -> set[str]:
    """Every name a locus could be recorded under for this target.

    Parameters
    ----------
    target : `tom_targets.models.Target`
        The target to name.

    Returns
    -------
    set of str
        The target's own name plus any aliases.

    Notes
    -----
    Save records key on `locus_id`, a plain string, and a locus may be
    recorded under either the target's name or an alias -- mirroring how
    `locus_is_saved_as_target` decides a locus is saved.

    Aliases are best-effort: during a cascading delete they may already be
    gone, and a missing alias must not stop the caller.
    """
    names = {getattr(target, "name", None)}
    try:
        names.update(target.aliases.values_list("name", flat=True))
    except Exception:  # noqa: BLE001
        pass
    return {name for name in names if name}


def target_saver_usernames(target) -> list[str]:
    """Who has saved this target, one entry per team.

    Parameters
    ----------
    target : `tom_targets.models.Target`
        The target to inspect.

    Returns
    -------
    list of str
        Usernames of every PI with a save record for it, sorted.

    Notes
    -----
    `AntaresTargetSave` is unique per (locus, user), so a second row means a
    second team asked to save the same locus and was given access to the one
    shared target. Counting rows is therefore counting teams.
    """
    from goats_tom.models import AntaresTargetSave  # noqa: PLC0415

    return sorted(
        AntaresTargetSave.objects.filter(
            locus_id__in=target_locus_names(target)
        )
        .values_list("saved_by__username", flat=True)
        .distinct()
    )


def is_shared_target(target) -> bool:
    """Whether more than one team holds this target.

    Parameters
    ----------
    target : `tom_targets.models.Target`
        The target to inspect.

    Returns
    -------
    bool
        `True` if two or more PIs have save records for it.

    Notes
    -----
    There is one `Target` per locus, shared between teams rather than
    duplicated (see `save_locus_as_target`). Deleting one therefore removes it
    from every team at once, including teams that neither asked for it to go
    nor can see who did -- so a shared target is refused deletion outright.
    """
    return len(target_saver_usernames(target)) > 1


def locus_is_saved_as_target(locus_id: str) -> bool:
    """Check whether a locus has already been saved as a `Target`.

    Checks both `Target.name` and each target's `TargetName` aliases
    (via `Target.names`, TOM Toolkit's own name+alias union) rather than
    just `Target.name` -- a locus could in principle be recorded as an
    alias on a target that was saved or renamed some other way, outside
    the paths this module controls, and we don't want to let someone
    create a duplicate target in that case.

    Parameters
    ----------
    locus_id : str
        ANTARES locus ID to check.

    Returns
    -------
    bool
        Whether any existing `Target` has this locus_id as its name or as
        one of its aliases.
    """
    # `Target.names` is a Python-level property (name + aliases), not a
    # queryable field, so we check the two underlying sources directly at
    # the database level rather than loading every target into Python.
    if Target.objects.filter(name=locus_id).exists():
        return True
    return Target.objects.filter(aliases__name=locus_id).exists()


def _target_perm(target, action: str) -> str:
    """Build a guardian permission string for a target instance.

    Parameters
    ----------
    target : `Target`
        The target the permission applies to. Only its model metadata is
        read.
    action : str
        One of ``"view"``, ``"change"``, ``"delete"``.

    Returns
    -------
    str
        e.g. ``"tom_targets.view_target"``.

    Notes
    -----
    Derived from the instance's own `_meta.app_label` rather than hardcoding
    ``tom_targets``. On the pinned TOM Toolkit (2.32.2) these are the same
    string -- TOM hardcodes it in `Target.give_user_access` -- but a TOM may
    swap in its own target model under a different app label, and later TOM
    versions resolve the label dynamically for exactly that reason. Reading
    it from the instance works on any version without depending on a helper
    whose location has moved between releases.
    """
    return f"{target._meta.app_label}.{action}_target"


def share_target_with_group(target, group, full_access: bool = False) -> None:
    """Grant a group access to an existing target.

    Parameters
    ----------
    target : `Target`
        The target to share.
    group : `django.contrib.auth.models.Group`
        The group to grant access to.
    full_access : bool, optional
        If `True`, grant change and delete alongside view -- used for the
        team that created the target. If `False` (the default), grant view
        only.

    Notes
    -----
    Later teams get view only, deliberately. `Target.give_user_access`
    grants view, change *and* delete together, so granting that to every
    team that saves a shared locus would let any of them edit or delete a
    target another team is actively observing. The team that saved it first
    keeps change and delete; everyone else can look but not alter.

    Group-level permissions are how TOM itself shares targets (see
    `tom_targets.forms`), so a target shared this way behaves normally
    everywhere else in GOATS rather than only on the ANTARES dashboard.
    """
    assign_perm(_target_perm(target, "view"), group, target)
    if full_access:
        assign_perm(_target_perm(target, "change"), group, target)
        assign_perm(_target_perm(target, "delete"), group, target)


def _existing_target(locus_id: str):
    """Return the `Target` already representing this locus, or `None`.

    Parameters
    ----------
    locus_id : str
        The locus to look for.

    Returns
    -------
    `Target` or None
        The existing target, matched on name or alias.

    Notes
    -----
    Checks aliases as well as `Target.name`, matching
    `locus_is_saved_as_target` -- a locus may be recorded as an alias on a
    target saved or renamed by some other path, and that target is still the
    one to share rather than a reason to create a second.
    """
    target = Target.objects.filter(name=locus_id).first()
    if target is not None:
        return target
    return Target.objects.filter(aliases__name=locus_id).first()


def _record_save(locus_id: str, target, saved_by) -> None:
    """Record that `saved_by` saved this locus.

    Parameters
    ----------
    locus_id : str
        The locus saved.
    target : `Target`
        The target, used only for logging.
    saved_by : `django.contrib.auth.models.User` or None
        The saving user. `None` records nothing, since the row exists to
        attribute a save to a person.

    Notes
    -----
    Failures are logged rather than raised, for the same reason as the light
    curve step: losing attribution should not discard a target that was
    otherwise saved successfully. `update_or_create` keeps a repeat save by
    the same user idempotent.
    """
    if saved_by is None:
        return
    try:
        AntaresTargetSave.objects.update_or_create(
            locus_id=locus_id, saved_by=saved_by
        )
    except Exception:
        logger.exception(
            "Saved/shared target id=%s for locus %s, but failed to record "
            "who saved it.",
            target.pk,
            locus_id,
        )


def _share_existing_target(
    target, locus_id: str, saved_by=None, share_with_group=None
) -> Target:
    """Grant a second team access to a target that already exists.

    Parameters
    ----------
    target : `Target`
        The existing target for this locus.
    locus_id : str
        The locus being saved.
    saved_by : `django.contrib.auth.models.User`, optional
        The user saving it now.
    share_with_group : `django.contrib.auth.models.Group`, optional
        Their team.

    Returns
    -------
    `Target`
        The same target, now shared.

    Notes
    -----
    View access only, for both the user and their group: the team that
    created the target keeps change and delete (see
    `share_target_with_group`). Deliberately does not re-fetch the locus from
    ANTARES or re-ingest its light curve -- the data is already attached to
    this target and shared along with it, so repeating that work would cost
    an HTTP round trip to produce duplicates.
    """
    if saved_by is not None:
        assign_perm(_target_perm(target, "view"), saved_by, target)
    if share_with_group is not None:
        share_target_with_group(target, share_with_group, full_access=False)

    _record_save(locus_id, target, saved_by)

    logger.info(
        "Shared existing target id=%s for locus %s with user=%s group=%s "
        "(view only).",
        target.pk,
        locus_id,
        getattr(saved_by, "username", None),
        getattr(share_with_group, "name", None),
    )
    return target


def save_locus_as_target(locus_id: str, saved_by=None, share_with_group=None) -> Target:
    """Fetch a locus from ANTARES and save it as a GOATS `Target`, including
    its light curve.

    Mirrors what `Antares2GoatsViewSet.perform_create` does for the
    browser-extension save path -- target creation plus light curve
    ingestion -- so all three save paths (extension, the subscription's
    auto-save option, and the dashboard's manual save) produce targets in
    the same shape.

    Parameters
    ----------
    locus_id : str
        ANTARES locus ID to fetch and save.
    saved_by : `django.contrib.auth.models.User`, optional
        The user this save should be attributed to -- `request.user` for
        the dashboard's manual "Save selected" button, or the
        subscription's `owner` for the consumer's auto-save.
        Recorded in `goats_tom.models.AntaresTargetSave`, since TOM
        Toolkit's `Target` has no "created by" field of its own. `None`
        leaves the save unattributed (shown as unknown on the dashboard)
        rather than guessing at a user.
    share_with_group : `django.contrib.auth.models.Group`, optional
        The saving user's team, granted access to the target alongside them.
        Normally the PI group behind the dashboard the save came from (see
        `goats_tom.models.AntaresPIGroup`). Sharing with the group rather
        than only the individual is what lets a PI's whole team see targets
        a student saved, and is how the one-target-per-locus model works at
        all. `None` shares with nobody, leaving the target visible only to
        `saved_by`.

    Returns
    -------
    `Target`
        The target, whether newly created by this call or already existing
        and now shared with `saved_by`. Returned even if light curve
        ingestion fails after target creation -- that failure is logged, not
        raised (see notes below).

    Raises
    ------
    SaveLocusError
        If the locus can't be fetched from ANTARES, or if the target
        itself fails to save. Notably *not* raised when the target already
        exists: that is the shared-target case and is handled additively
        (see the module docstring), not as an error.
        Does NOT raise if only light curve ingestion fails after the target
        was already saved successfully.

    Notes
    -----
    Two paths. If no target exists for this locus, one is created and the
    saver -- and their group -- get full access to it. If a target already
    exists, nothing is re-fetched or re-created: the existing target is
    simply shared with the saver and their group, at view level only, so the
    team that created it retains change and delete.
    """
    existing = _existing_target(locus_id)
    if existing is not None:
        return _share_existing_target(
            existing, locus_id, saved_by=saved_by, share_with_group=share_with_group
        )

    broker = tom_alerts_get_service_class("ANTARES")()

    alert = next(broker.fetch_alerts({"locusid": locus_id}), None)
    if alert is None:
        raise SaveLocusError(f"No ANTARES alert data found for locus {locus_id!r}.")

    try:
        target, extras, aliases = broker.to_target(alert)
        target.save(extras=extras, names=aliases)
        # Attribution is recorded here, immediately, rather than after the
        # light curve work below. The dashboard decides "is this saved?" from
        # the Target and "who saved it?" from AntaresTargetSave, so any gap
        # between the two shows the locus as saved by "Unknown" -- which is
        # what a poll landing during light curve ingestion used to see. That
        # ingestion is a network fetch plus several writes, so the window was
        # easily wide enough to hit on the very first poll after saving.
        _record_save(locus_id, target, saved_by)
    except Exception as exc:
        raise SaveLocusError(
            f"Failed to save locus {locus_id!r} as a target: {exc}"
        ) from exc

    # Matches the browser extension's save path (see
    # Antares2GoatsViewSet.perform_create) so targets saved from GOATS
    # itself get the same light curve data extension-saved targets do.
    # Kept as a separate try/except from the target save above: a light
    # curve failure shouldn't discard an already-created target, just be
    # logged as a partial success.
    try:
        lightcurve_data = broker.process_lightcurve_data(alert=alert)
        # Same user and group the target itself is granted to below, so the
        # light curve is visible to exactly whoever the target is.
        dp = broker.create_lightcurve_dp(
            target,
            lightcurve_data,
            user=saved_by,
            share_with_group=share_with_group,
        )
        broker.create_reduced_datums(dp)
    except Exception:
        logger.exception(
            "Saved target id=%s for locus %s, but failed to ingest its "
            "light curve.",
            target.pk,
            locus_id,
        )

    # Grant the saving user access to the target they just created.
    # TOM Toolkit's `TARGET_DEFAULT_PERMISSION` defaults to PRIVATE, and
    # `targets_for_user` (which backs the target list/detail pages) shows
    # a non-superuser only public targets plus private ones they hold an
    # explicit guardian permission on. Superusers bypass that filter
    # entirely -- which is exactly why an admin could see these targets
    # and the user who actually saved them could not. TOM's own create
    # path grants these permissions; this save path previously did not.
    # Uses `Target.give_user_access` rather than calling guardian's
    # `assign_perm` directly, so the exact set of permissions granted
    # stays whatever TOM Toolkit defines it to be.
    if saved_by is not None:
        try:
            target.give_user_access(saved_by)
        except Exception:
            logger.exception(
                "Saved target id=%s for locus %s, but failed to grant "
                "access to user id=%s -- they may not be able to see it.",
                target.pk,
                locus_id,
                saved_by.pk,
            )
    else:
        logger.warning(
            "Saved target id=%s for locus %s with no attributed user, so "
            "no access was granted -- with the default PRIVATE "
            "permission only superusers will see it.",
            target.pk,
            locus_id,
        )

    # Share with the saver's team, at full access -- this is the team that
    # created the target, so they keep change and delete. Any team that saves
    # the same locus later gets view only (see `_share_existing_target`).
    # Without this, a target a student saved would be invisible to their PI
    # and the rest of the group, since TARGET_DEFAULT_PERMISSION is PRIVATE.
    if share_with_group is not None:
        try:
            share_target_with_group(target, share_with_group, full_access=True)
        except Exception:
            logger.exception(
                "Saved target id=%s for locus %s, but failed to share it "
                "with group %s -- their team may not be able to see it.",
                target.pk,
                locus_id,
                getattr(share_with_group, "name", None),
            )

    logger.info("Saved ANTARES locus %s as target id=%s.", locus_id, target.pk)
    return target
