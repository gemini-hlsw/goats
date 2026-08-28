"""Per-user scoping for GOATS querysets.

GOATS was written for one astronomer on one machine, where every row in the
database belonged to the only person who could log in. A shared deployment
breaks that assumption everywhere at once: a view that returns
``Model.objects.all()`` is correct on a laptop and a data leak on a server.

Two different ownership shapes exist, and conflating them is the mistake this
module exists to prevent.

**Owned directly.** GOATS' own models -- an `AntaresStreamSubscription` and
everything hanging off it -- reach a user through a foreign key, so they are
scoped with a plain filter such as ``owner`` or ``subscription__owner``.

**Owned through a target.** The DRAGONS models have no owner at all. A
`DRAGONSRun` belongs to an `ObservationRecord`, which belongs to a `Target`,
and it is the *target* that carries per-object permissions. TOM Toolkit
already scopes its own models this way with `get_objects_for_user`, but
GOATS' viewsets query the DRAGONS models directly and so bypass it entirely.
Those are scoped by joining back to the target and asking guardian.

Notes
-----
Scoping is applied in `get_queryset`, which covers list *and* detail: DRF
retrieves a single object from the same queryset, so an out-of-scope row is a
404 rather than someone else's data. Fixing only the list endpoints would
leave every ``/api/thing/<id>/`` readable by changing the number in the URL,
which is the easier attack of the two.
"""

__all__ = ["ScopedQuerySetMixin", "scope_to_user"]

import logging

from django.conf import settings
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def scope_to_user(
    queryset: QuerySet,
    user,
    *,
    owner_path=None,
    target_path=None,
    dataproduct_path=None,
):
    """Restrict `queryset` to rows `user` may see.

    Parameters
    ----------
    queryset : `QuerySet`
        The unscoped queryset.
    user : `django.contrib.auth.models.User`
        The requesting user.
    owner_path : str, optional
        ORM path from the model to its owning user, e.g. ``"owner"`` or
        ``"subscription__owner"``.
    target_path : str, optional
        ORM path from the model to the `Target` whose view permission
        governs it, e.g. ``"observation_record__target"``.
    dataproduct_path : str, optional
        ORM path from the model to the `DataProduct` whose view permission
        governs it, e.g. ``"observation_record__dataproduct"``.

    Returns
    -------
    `QuerySet`
        The scoped queryset. Empty for an anonymous user.

    Raises
    ------
    ValueError
        If neither path is given. Refusing is deliberate -- a scoping helper
        that silently returned everything when misconfigured would be worse
        than not having one, because the call site would *look* protected.

    Notes
    -----
    A superuser is not exempted. Staff on a shared instance still have no
    business reading a PI's proprietary targets by default, and an exemption
    here would apply to every endpoint at once with no way to see it from the
    call site.
    """
    if owner_path is None and target_path is None and dataproduct_path is None:
        raise ValueError(
            "scope_to_user needs owner_path, target_path or dataproduct_path; "
            "refusing to return an unscoped queryset."
        )

    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if owner_path is not None:
        return queryset.filter(**{owner_path: user})

    from guardian.shortcuts import get_objects_for_user  # noqa: PLC0415

    if dataproduct_path is not None:
        # Follows the data, not the target.
        #
        # An observation record is shared for coordination -- collaborators
        # on a target should see that an observation was triggered -- while
        # its data products stay private to whoever triggered it. A DRAGONS
        # run is a reduction *of those files*, so scoping it by the target
        # would show one PI's reduction to everyone who can see the target,
        # while the files it reduced stayed hidden. Scoping by data product
        # keeps the run with the data it belongs to.
        from tom_dataproducts.models import DataProduct  # noqa: PLC0415

        visible = get_objects_for_user(
            user, f"{DataProduct._meta.app_label}.view_dataproduct"
        )
        return queryset.filter(**{f"{dataproduct_path}__in": visible}).distinct()

    # Target-permission scoping, matching what TOM Toolkit does for its own
    # models so the two cannot disagree about who may see a target.
    from tom_targets.models import Target  # noqa: PLC0415

    visible = get_objects_for_user(
        user, f"{Target._meta.app_label}.view_target"
    )
    return queryset.filter(**{f"{target_path}__in": visible})


class ScopedQuerySetMixin:
    """Restrict a viewset's queryset to the requesting user.

    Set exactly one of `owner_path` or `target_path` on the subclass.

    Attributes
    ----------
    owner_path : str or None
        ORM path to the owning user.
    target_path : str or None
        ORM path to the governing `Target`.

    Notes
    -----
    Calls `super().get_queryset()` first, so a viewset that already narrows
    its queryset -- by observation record, say -- keeps doing so and has this
    applied on top. Ordering matters: scoping last means a subclass cannot
    accidentally widen what it is allowed to see.

    Inert unless ``GOATS_ENFORCE_SCOPING`` is on, which
    ``environments/server.py`` sets. On a single-astronomer desktop install
    every row already belongs to the only user, so scoping changes nothing
    there -- but only if targets have been assigned to that user's groups,
    which a laptop install has no reason to have done. Leaving it off by
    default keeps the desktop behaving exactly as before, which is the
    invariant this work is held to.
    """

    owner_path: str | None = None
    target_path: str | None = None
    dataproduct_path: str | None = None

    def get_queryset(self) -> QuerySet:
        """Return the queryset, scoped to the requesting user."""
        queryset = super().get_queryset()
        if not getattr(settings, "GOATS_ENFORCE_SCOPING", False):
            return queryset
        return scope_to_user(
            queryset,
            getattr(self.request, "user", None),
            owner_path=self.owner_path,
            target_path=self.target_path,
            dataproduct_path=self.dataproduct_path,
        )
