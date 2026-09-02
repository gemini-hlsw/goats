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

__all__ = [
    "DRAGONSRunObjectPermissions",
    "DataProductObjectPermissions",
    "ReducedDatumObjectPermissions",
    "TargetObjectPermissions",
    "may_reduce_observation",
    "grant_dataproduct_permissions",
    "grant_observation_permissions",
    "has_assigned_perm",
    "may_delete_selection",
    "may_delete_target",
    "target_is_public",
    "undeletable_dataproducts",
]

import logging

from django.conf import settings
from guardian.shortcuts import get_users_with_perms
from rest_framework import permissions

logger = logging.getLogger(__name__)

DELETE_DATAPRODUCT = "delete_dataproduct"


def has_assigned_perm(user, obj, perms) -> bool:
    """Whether `user` holds one of `perms` on `obj` as an *assigned* row.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user being checked.
    obj : `django.db.models.Model`
        The object to read permissions from.
    perms : `list[str]`
        Permission codenames, without the app label -- guardian's form.

    Returns
    -------
    `bool`
        True when guardian holds a matching row for the user, directly or
        through one of their groups.

    Notes
    -----
    **The single place this question is asked.** It was previously asked in
    four places with four copies of the same guardian call, which is how the
    ingestion banner came to be fixed on one page and not the other. One
    implementation means the next change lands everywhere at once.

    `user.has_perm` cannot answer it: Django's `ModelBackend` returns `True`
    for any superuser before guardian is consulted, so every ordinary
    permission call is already a bypass. This reads the assigned rows
    directly, which `get_users_with_perms` does without special-casing
    anybody.

    `with_group_users=True` so a grant made to a group counts, matching how
    sharing works everywhere else.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    holders = get_users_with_perms(
        obj,
        only_with_perms_in=list(perms),
        with_group_users=True,
    )
    return holders.filter(pk=user.pk).exists()


def undeletable_dataproducts(user, products) -> list:
    """Return the data products in `products` that `user` may not delete.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user attempting the deletion.
    products : iterable of `tom_dataproducts.models.DataProduct`
        The products the operation would destroy.

    Returns
    -------
    `list`
        The products with no assigned delete row for this user. Empty when
        every one of them may be deleted, which is the only case a caller
        should let through.

    Notes
    -----
    Empty in target-only mode, where a desktop install has one user who owns
    everything and there are no per-object rows to read.

    **Every product, not a model-wide question.** A cascade that silently
    skipped the files it could not delete would be worse than a refusal: the
    caller has already told the user their observation or target is going
    away, and a partial deletion leaves them believing something happened
    that did not.

    Refusals by a superuser are logged, because an administrator who is
    refused should be able to find out why and the refusal should leave a
    trace. `manage.py grant_delete` is the deliberate path when it is
    genuinely needed.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return []
    refused = [
        product
        for product in products
        if not has_assigned_perm(user, product, [DELETE_DATAPRODUCT])
    ]
    if refused and getattr(user, "is_superuser", False):
        logger.warning(
            "Superuser %s was refused deletion of %d data product(s): %s. "
            "Deletion is not granted by superuser status; use `manage.py "
            "grant_delete` if this is intended.",
            user.username,
            len(refused),
            ", ".join(
                str(getattr(p, "product_id", p.pk)) for p in refused[:10]
            ),
        )
    return refused

OBSERVATION_ACTIONS = ("view", "change", "delete")


def _record_observation_owner(record, user) -> None:
    """Set `record.user` if it is not already set.

    Parameters
    ----------
    record : `tom_observations.models.ObservationRecord`
        The record to stamp.
    user : `django.contrib.auth.models.User` or None
        The creator.

    Notes
    -----
    Does not overwrite an existing owner. `ObservationCreateView` already
    sets one upstream, and re-stamping it here would silently reassign an
    observation if this function were ever called on an existing record.

    Saves only the one field, so nothing else on a record another request
    may be holding gets written back.

    Failures are logged, never raised. By the time this runs the observation
    may already be scheduled at the observatory; losing that over a database
    write would be far worse than an unstamped row an administrator can
    repair.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return
    if getattr(record, "user_id", None) is not None:
        return

    try:
        record.user = user
        record.save(update_fields=["user"])
    except Exception:
        logger.exception(
            "Could not record %s as the owner of observation %s.",
            getattr(user, "username", None),
            getattr(record, "observation_id", record),
        )


def grant_observation_permissions(record, user) -> None:
    """Record `user` as the owner of an observation and grant them access.

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
    **Two things, deliberately in one place.** It sets `record.user` and it
    assigns the guardian rows. They were separate, and drifted: every caller
    assigned permissions and none set the field, so records were visible and
    manageable by the right person while their `user` column stayed NULL.

    Nothing read it, which is why that went unnoticed for so long. Scoping
    goes through guardian; `may_reduce_observation` goes through guardian.
    `VOSpaceStorage` is the first thing that has to *name* an owner rather
    than test one -- it needs a username to build a VOSpace path -- and a
    NULL there has no safe default, because guessing writes a PI's
    proprietary data into somebody else's account.

    Upstream is inconsistent about this and that is the root of it.
    `ObservationCreateView` sets `user=self.request.user`;
    `AddExistingObservationView` does not; and
    `ObservationRecordSerializer.create` passes ``**validated_data``
    straight through without ever reading `request.user`, which is the path
    `gemini_trigger` uses. Setting it here covers all of them, because every
    GOATS creation path already calls this function.

    No-op when ``TARGET_PERMISSIONS_ONLY`` is True, where the target governs
    everything beneath it and these rows would be unused. **The owner is
    still recorded**, before that check: it is a fact about who made the
    observation, not a permission, and the storage layer needs it in either
    mode.

    Granted to the user alone, not to their groups. Sharing is theirs to
    decide afterwards from the observation page; doing it here would make
    the choice for them, and an observation shared by default is exactly
    what the per-object model exists to avoid.

    Change and delete come with view because the creator should be able to
    manage what they made. Recipients of a share get view only, which is
    what stops access being passed on further.
    """
    _record_observation_owner(record, user)

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


class AssignedObjectPermissions(permissions.BasePermission):
    """Require an *assigned* guardian row for write methods, with no superuser bypass.

    Notes
    -----
    DRF ships `DjangoObjectPermissions`, and it is not usable here for the
    same reason `user.has_perm` is not usable in
    `goats_tom.views.dataproduct_delete`: it goes through the authentication
    backends, and Django's `ModelBackend` returns `True` for any superuser
    before guardian is ever consulted. The assigned rows have to be read
    directly, which `get_users_with_perms` does without special-casing
    anybody.

    `with_group_users=True` so a grant made to a group counts, matching how
    sharing works everywhere else.

    Inert when ``TARGET_PERMISSIONS_ONLY`` is True. A desktop install has one
    user who owns everything, no per-object rows exist to read, and a
    guardrail against deleting somebody else's data has nobody to protect --
    the same branch every other permission check in GOATS opens with.
    """

    #: Permission codenames required per HTTP method. Safe methods are absent
    #: deliberately: read access is enforced by the viewset's `get_queryset`,
    #: which returns only rows the user may view, so an object that reaches
    #: here has already passed a read check. Creation is absent for the same
    #: reason it cannot be checked -- there is no object yet.
    perms_map: dict[str, list[str]] = {}

    def get_permission_object(self, obj):
        """Return the object whose assigned rows govern `obj`.

        Parameters
        ----------
        obj : `django.db.models.Model`
            The object the request is acting on.

        Returns
        -------
        `django.db.models.Model` or None
            The object to read permissions from, or `None` when no such
            object can be resolved -- which denies the request.
        """
        return obj

    def has_permission(self, request, view) -> bool:
        """Reject anonymous callers before any object is fetched.

        Parameters
        ----------
        request : `rest_framework.request.Request`
            The incoming request.
        view : `rest_framework.views.APIView`
            The view handling it.

        Returns
        -------
        `bool`
            True when the caller is authenticated.
        """
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        """Check the assigned rows for the permission this method needs.

        Parameters
        ----------
        request : `rest_framework.request.Request`
            The incoming request.
        view : `rest_framework.views.APIView`
            The view handling it.
        obj : `django.db.models.Model`
            The object being acted on.

        Returns
        -------
        `bool`
            True when the request may proceed.
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return True

        required = self.perms_map.get(request.method, [])
        if not required:
            return True

        target = self.get_permission_object(obj)
        if target is None:
            # Nothing to read permissions from. Refuse rather than guess:
            # a write we cannot attribute is exactly the case that should
            # not be allowed through.
            logger.warning(
                "Refused %s on %s %s: no object to read permissions from.",
                request.method,
                obj._meta.model_name,
                getattr(obj, "pk", obj),
            )
            return False

        holders_check = has_assigned_perm(request.user, target, required)
        if holders_check:
            return True

        if request.user.is_superuser:
            # Logged for the same reason the delete views log it: an
            # administrator who is refused should be able to find out why,
            # and the refusal should leave a trace.
            logger.warning(
                "Superuser %s was refused %s on %s %s. %s is not granted by "
                "superuser status; use `manage.py grant_delete` if this is "
                "intended.",
                request.user.username,
                request.method,
                obj._meta.model_name,
                getattr(obj, "pk", obj),
                ", ".join(required),
            )
        return False


class DataProductObjectPermissions(AssignedObjectPermissions):
    """Object permissions for the data product API endpoints.

    Notes
    -----
    This closes the hole that made the superuser delete ban ineffective in
    practice. `DataProductDeleteView` and
    `DeleteObservationDataProductsView` were both fixed, but
    `tom_dataproducts.api_views.DataProductViewSet` carries
    `DestroyModelMixin` and declares only ``view_dataproduct``, and GOATS
    sets ``DEFAULT_PERMISSION_CLASSES`` to an empty list -- so
    ``DELETE /api/dataproducts/<pk>/`` performed no permission check at all.
    Anything a user could *see* they could destroy, and a superuser sees
    everything.

    Change is required for `PUT` and `PATCH` to match
    `DataProductTypeViewSet`, where retagging is treated as a write because
    it can delete the photometry derived from a file. Delete is separate and
    stricter: sharing grants view and, at full access, change -- never
    delete.
    """

    perms_map = {
        "PUT": ["change_dataproduct"],
        "PATCH": ["change_dataproduct"],
        "DELETE": ["delete_dataproduct"],
    }


class ReducedDatumObjectPermissions(AssignedObjectPermissions):
    """Object permissions for the reduced datum API endpoints.

    Notes
    -----
    Governed by the **parent data product**, not by rows on the datum
    itself. Nothing in GOATS assigns per-object permissions to a
    `ReducedDatum` -- upstream grants ``view_reduceddatum`` to selected
    groups on upload and nothing else does -- so requiring an assigned row
    here would refuse the owning PI along with everybody else.

    Deriving it from the file the points came from is also the more honest
    rule: a photometry point is part of the data product it was extracted
    from, and deleting the file deletes them anyway.

    A datum with no data product -- broker-ingested photometry, the ANTARES
    light curves -- has no file to inherit from, so it falls back to
    ``change_target``.
    """

    perms_map = {
        "PUT": ["change_dataproduct"],
        "PATCH": ["change_dataproduct"],
        "DELETE": ["delete_dataproduct"],
    }

    #: Applied instead of `perms_map` when the datum has no data product.
    target_perms_map = {
        "PUT": ["change_target"],
        "PATCH": ["change_target"],
        "DELETE": ["change_target"],
    }

    def get_permission_object(self, obj):
        """Return the parent data product, or the target when there is none.

        Parameters
        ----------
        obj : `tom_dataproducts.models.ReducedDatum`
            The datum being acted on.

        Returns
        -------
        `django.db.models.Model` or None
            The data product the datum came from, its target if it came from
            no file, or `None` if it has neither.
        """
        return getattr(obj, "data_product", None) or getattr(obj, "target", None)

    def has_object_permission(self, request, view, obj) -> bool:
        """Check against the data product, or the target when there is none.

        Parameters
        ----------
        request : `rest_framework.request.Request`
            The incoming request.
        view : `rest_framework.views.APIView`
            The view handling it.
        obj : `tom_dataproducts.models.ReducedDatum`
            The datum being acted on.

        Returns
        -------
        `bool`
            True when the request may proceed.
        """
        if getattr(obj, "data_product", None) is None:
            # Swap the permission names for the fallback object. Done here
            # rather than in `get_permission_object` because the required
            # permission and the object it is read from have to change
            # together, and splitting them is how they drift apart.
            original = self.perms_map
            try:
                self.perms_map = self.target_perms_map
                return super().has_object_permission(request, view, obj)
            finally:
                self.perms_map = original
        return super().has_object_permission(request, view, obj)


PUBLIC_GROUP_NAME = "Public"


def target_is_public(target) -> bool:
    """Whether `target` is shared with the ``Public`` group.

    Parameters
    ----------
    target : `tom_targets.models.Target`
        The target to test.

    Returns
    -------
    `bool`
        True when the ``Public`` group holds any permission on it.

    Notes
    -----
    "Public" is an ordinary Django group that TOM's target form offers
    alongside the user's own groups; ticking it assigns view, change **and**
    delete to every member, which in practice is everyone with an account.
    There is no `is_public` flag to read -- the group grant *is* the state --
    so this asks guardian which groups hold permissions and looks for it by
    name.
    """
    from guardian.shortcuts import get_groups_with_perms  # noqa: PLC0415

    return (
        get_groups_with_perms(target)
        .filter(name=PUBLIC_GROUP_NAME)
        .exists()
    )


def may_delete_target(user, target) -> bool:
    """Whether `user` may delete `target`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user attempting the deletion.
    target : `tom_targets.models.Target`
        The target in question.

    Returns
    -------
    `bool`
        True when the deletion may proceed.

    Notes
    -----
    Two rules, and the public one is an exception to everything else in this
    module.

    **A public target may be deleted only by a superuser.** The group grant
    that makes a target public also grants delete to every member of
    ``Public``, so the ordinary rule below would let *any* registered user
    delete it -- worse than no rule at all. Inverting it for this one case
    keeps a target that belongs to everybody from being removed by anybody.
    The consequence is deliberate and users will notice it: whoever created
    a public target can no longer delete it themselves and has to ask an
    administrator.

    **Every other target follows the rule the rest of GOATS follows**: an
    assigned `delete_target` row, read directly, with no superuser bypass.

    This is the one place a superuser *keeps* delete while losing it
    everywhere else, which reads as a contradiction next to the delete ban
    and is not one: everywhere else the question is whose data is being
    destroyed, and a public target is nobody's in particular.

    Inert in target-only mode, where a desktop install has one user who owns
    everything.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if target_is_public(target):
        return bool(getattr(user, "is_superuser", False))
    return has_assigned_perm(user, target, ["delete_target"])


def may_delete_selection(user, selection, permission) -> bool:
    """Whether `user` may delete a saved selection.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user attempting the deletion.
    selection : `django.db.models.Model`
        A `TargetList`, `ObservationGroup` or `DataProductGroup`.
    permission : `str`
        The delete permission codename, without the app label.

    Returns
    -------
    `bool`
        True when the deletion may proceed.

    Notes
    -----
    Saved selections hold no science data -- a name and a list of items --
    so this is a lighter case than the delete ban, and it is here for the
    same reason: the selection is somebody's work, an administrator deleting
    one by misreading a page cannot undo it, and superuser status was the
    only thing letting them.

    Upstream leaks this three different ways for three models.
    `TargetGroupingDeleteView` and `ObservationGroupDeleteView` check with
    `has_perm`, which returns True for a superuser before guardian is
    consulted. GOATS' own data product group view scopes with
    `get_objects_for_user`, whose ``with_superuser`` argument defaults to
    True and does the same thing less visibly. One rule replaces all three.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return True
    return has_assigned_perm(user, selection, [permission])


def may_reduce_observation(user, observation_record) -> bool:
    """Whether `user` may run or destroy a reduction on `observation_record`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user attempting the action.
    observation_record : `tom_observations.models.ObservationRecord`
        The record the reduction belongs to.

    Returns
    -------
    `bool`
        True when the action may proceed.

    Notes
    -----
    **One predicate for starting a reduction and for deleting one**, which is
    the point of it existing. A run belongs to whoever could have created it;
    asking a different question on the way out is how a rule drifts.

    The condition is full access to the observation --
    ``change_observationrecord`` -- because that is what the observation
    detail page already uses to decide whether to render the DRAGONS panel at
    all. Sharing grants view, and at full access change; a read-only
    recipient sees the observation and its data and cannot act on it. That
    was already the intended rule and was enforced only by hiding the panel,
    which is not an access check -- the same gap `GOAQueryFormView` closes on
    the GOA side.

    Uses `has_perm`, not `has_assigned_perm`, and so **admits superusers**.
    That is the settled decision, not an inherited default: administrators
    may reduce, and may delete the runs they can start.

    It does not contradict the delete ban, which is about *data products*.
    Destroying a run removes its own output directory -- the reduction's
    own output -- and does not touch the PI's raw files, which
    `DataProductObjectPermissions` still governs with no superuser bypass.
    Reduction is not destructive to the data it reads, so it sits outside
    that ban rather than against it.

    `can_edit_observation` on the observation detail page is computed the
    same way, so the panel a superuser can see and the actions behind it
    now agree. They did not before: the panel was visible and nothing
    behind it checked anything.

    Inert in target-only mode, as every check in this module is.
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm(
            "tom_observations.change_observationrecord", observation_record
        )
    )


class DRAGONSRunObjectPermissions(AssignedObjectPermissions):
    """Object permissions for the DRAGONS run endpoints.

    Notes
    -----
    Subclasses `AssignedObjectPermissions` for its anonymous refusal and its
    target-only branch, but answers the question with
    `may_reduce_observation` rather than by reading assigned rows -- see that
    function for why, and for the superuser note.

    `DRAGONSRunsViewSet` previously declared only
    `permissions.IsAuthenticated`, so `DELETE /api/dragonsruns/<pk>/` removed
    a reduction's output directory with `shutil.rmtree` for any authenticated
    caller. `ScopedQuerySetMixin` narrows the *list*, which is a different
    question, and is inert unless ``GOATS_ENFORCE_SCOPING`` is set -- so on a
    default install nothing stood in the way at all.
    """

    perms_map = {
        "PUT": ["change_observationrecord"],
        "PATCH": ["change_observationrecord"],
        "DELETE": ["change_observationrecord"],
    }

    def has_object_permission(self, request, view, obj) -> bool:
        """Check `obj`'s observation record rather than assigned rows."""
        if settings.TARGET_PERMISSIONS_ONLY:
            return True
        if not self.perms_map.get(request.method):
            return True

        record = getattr(obj, "observation_record", None)
        if record is None:
            logger.warning(
                "Refused %s on DRAGONS run %s: no observation record to read "
                "permissions from.",
                request.method,
                getattr(obj, "pk", obj),
            )
            return False

        if may_reduce_observation(request.user, record):
            return True

        logger.warning(
            "%s was refused %s on DRAGONS run %s: no change_observationrecord "
            "on observation %s.",
            getattr(request.user, "username", request.user),
            request.method,
            getattr(obj, "pk", obj),
            getattr(record, "pk", record),
        )
        return False


class TargetObjectPermissions(AssignedObjectPermissions):
    """Object permissions for the target API endpoints.

    Notes
    -----
    Delegates to `may_delete_target`, so the API and
    `goats_tom.views.target_delete` answer with the same code. Writing the
    two target rules a second time is how they drift, and this pair is
    subtle enough that a drifted copy would not look wrong.

    Closes two holes at once, which is why it matters. `TargetViewSet`
    declared only `permissions.IsAuthenticated`, leaving upstream's
    `get_queryset` as the sole guard -- and that calls
    `get_objects_for_user`, whose ``with_superuser`` default this document
    already names as "the same bypass wearing different clothes". So:

    - a **superuser** could delete any PI's target over the API, which the
      ordinary rule forbids; and
    - **any registered user** could delete a *public* target, since the
      ``Public`` group grants ``delete_target`` to every member -- the exact
      outcome the public-target inversion exists to prevent.

    Both rules were enforced on the web view and neither on the API beside
    it. That is the display/enforcement split again, on a different axis.

    Change is not listed. Editing a target is not destructive and upstream's
    ``change_target`` scoping already covers it; only deletion is narrowed
    here.
    """

    perms_map = {
        "DELETE": ["delete_target"],
    }

    def has_object_permission(self, request, view, obj) -> bool:
        """Apply both target rules, via `may_delete_target`."""
        if settings.TARGET_PERMISSIONS_ONLY:
            return True
        if request.method != "DELETE":
            return True

        if may_delete_target(request.user, obj):
            return True

        logger.warning(
            "%s was refused DELETE on target %s.",
            getattr(request.user, "username", request.user),
            getattr(obj, "pk", obj),
        )
        return False
