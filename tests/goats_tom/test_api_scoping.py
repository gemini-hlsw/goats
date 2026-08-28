"""Guards that every GOATS API viewset restricts what it returns.

The audit that produced `goats_tom.scoping` was a one-off sweep. Sweeps rot:
the next viewset somebody adds returns ``Model.objects.all()``, nobody
notices, and a single missed endpoint undoes the whole exercise. This test
walks the URL configuration on every run and fails if a viewset neither
scopes itself nor appears on an allowlist below.

The allowlist is the point. Making an endpoint unscoped becomes a line
somebody has to write, with a reason beside it, in a file that shows up in
review -- rather than the silent default.
"""

import pytest
from django.urls import get_resolver

from goats_tom.scoping import ScopedQuerySetMixin

#: Viewsets that legitimately return the same rows to everyone.
#:
#: Each entry needs a reason. "It seemed fine" is how the next leak gets
#: added.
PUBLIC_VIEWSETS = {
    # Reference data, identical for every user: the DRAGONS recipe library
    # and the module listing that describes it. Neither is derived from any
    # PI's observations.
    "BaseRecipeViewSet": "static DRAGONS recipe library",
    "RecipesModuleViewSet": "static DRAGONS module listing",
    # Health and version information about the installation itself.
    "SystemViewSet": "server status, no user data",
    # Write-only endpoints that create rows from a submitted payload and
    # never list anything. Scoping a queryset nobody reads would be noise.
    "Antares2GoatsViewSet": "create-only, no queryset read",
    "AstroDatalabViewSet": "create-only, no queryset read",
    "RunProcessorViewSet": "create-only, no queryset read",
    # Subclasses of TOM Toolkit viewsets, which already filter by the
    # target's view permission upstream -- see
    # `tom_dataproducts.api_views.DataProductViewSet.get_queryset`.
    "TargetViewSet": "scoped upstream by tom_targets",
    "DataProductsViewSet": "scoped upstream by tom_dataproducts",
    "ReducedDatumViewSet": "scoped upstream by tom_dataproducts",
    # `DataProductTypeViewSet` is deliberately absent: it is defined and
    # exported but never registered on the router, so it is unreachable and
    # this list -- which asserts its entries still exist -- would fail on it.
    # Its `get_queryset` was fixed anyway, so wiring it up later is safe.
    # Proxy the Gemini Program Platform using the requesting user's own GPP
    # credentials. They hold no local queryset, and what comes back is
    # whatever GPP decides that user may see.
    "GPPViewSet": "proxies GPP with the user's own credentials",
    "GPPProgramViewSet": "proxies GPP with the user's own credentials",
    "GPPObservationViewSet": "proxies GPP with the user's own credentials",
    "GPPFinderChartViewSet": "proxies GPP with the user's own credentials",
    "StatusViewSet": "server status, no user data",
    # Creates a saved selection and assigns it to the creator; it lists
    # nothing, so there is no queryset to scope. Its list, detail and delete
    # counterparts are scoped -- see `goats_tom.views.groups`.
    "GOATSDataProductGroupCreateView": "create-only, assigns perms to creator",
}

#: Modules whose `get_queryset` is already user-scoped.
#:
#: TOM Toolkit filters its own detail and list views through
#: `targets_for_user`, so a GOATS subclass that does not override
#: `get_queryset` inherits that scoping. Checking the *defining* module is
#: more honest than checking whether the subclass declares the method: the
#: question is whether scoping happens, not where it is written.
SCOPED_UPSTREAM_MODULES = ("tom_targets.", "tom_observations.", "tom_dataproducts.")


def _api_viewsets():
    """Yield every viewset class reachable from the URL configuration."""
    seen = {}
    patterns = list(get_resolver().url_patterns)
    while patterns:
        pattern = patterns.pop()
        nested = getattr(pattern, "url_patterns", None)
        if nested is not None:
            patterns.extend(nested)
            continue
        callback = getattr(pattern, "callback", None)
        cls = getattr(callback, "cls", None) or getattr(
            callback, "view_class", None
        )
        # Only GOATS' own views. TOM Toolkit's and third-party apps' are
        # their own responsibility, and asserting on them would fail for
        # reasons nobody here can fix.
        if cls is not None and cls.__module__.startswith("goats_tom"):
            seen[cls.__name__] = cls
    return seen


def test_every_goats_viewset_is_scoped_or_allowlisted():
    """A new endpoint must scope itself or be declared public on purpose."""
    unscoped = []
    for name, cls in sorted(_api_viewsets().items()):
        if name in PUBLIC_VIEWSETS:
            continue
        if issubclass(cls, ScopedQuerySetMixin):
            continue
        # Nothing to leak: no model data is exposed at all.
        if getattr(cls, "queryset", None) is None and getattr(
            cls, "model", None
        ) is None:
            continue
        # Scopes itself in its own `get_queryset`. Recognised rather than
        # allowlisted: an allowlist entry says "this view is exempt", which
        # would still be there long after somebody removed the scoping. This
        # checks the scoping is actually present.
        get_queryset = getattr(cls, "get_queryset", None)
        if get_queryset is not None and getattr(
            get_queryset, "__qualname__", ""
        ).startswith(cls.__name__ + "."):
            continue
        # Scoped by an upstream base class -- see SCOPED_UPSTREAM_MODULES.
        get_queryset = getattr(cls, "get_queryset", None)
        if get_queryset is not None and getattr(
            get_queryset, "__module__", ""
        ).startswith(SCOPED_UPSTREAM_MODULES):
            continue
        # Enforces access in `dispatch` rather than by narrowing the
        # queryset. `tom_common.views.UserUpdateView` does this: it redirects
        # a non-superuser editing somebody else's profile back to their own.
        # Equally effective, and a queryset filter would not be the natural
        # expression of it.
        dispatch = getattr(cls, "dispatch", None)
        if dispatch is not None and getattr(
            dispatch, "__module__", ""
        ).startswith(("tom_", "goats_tom.")):
            continue
        # Enforces access with a permission mixin instead of by narrowing the
        # queryset -- equally effective for a single-object view.
        if any(
            base.__name__
            in ("PermissionRequiredMixin", "Raise403PermissionRequiredMixin",
                "SuperuserRequiredMixin")
            for base in cls.__mro__
        ):
            continue
        unscoped.append(name)

    assert not unscoped, (
        "These GOATS viewsets return data without restricting it to the "
        f"requesting user: {unscoped}. Add `ScopedQuerySetMixin` with an "
        "`owner_path` or `target_path`, or add the name to PUBLIC_VIEWSETS "
        "with a reason."
    )


def test_scoped_viewsets_declare_a_path():
    """The mixin without a path would silently raise at request time.

    `scope_to_user` refuses to return an unscoped queryset, so a viewset that
    inherits the mixin but sets none of the paths fails on every request
    rather than leaking -- which is the right failure, but a poor way to discover
    it.
    """
    missing = [
        name
        for name, cls in _api_viewsets().items()
        if issubclass(cls, ScopedQuerySetMixin)
        and not (cls.owner_path or cls.target_path or cls.dataproduct_path)
    ]
    assert not missing, f"ScopedQuerySetMixin with no path declared: {missing}"


@pytest.mark.parametrize("name,reason", sorted(PUBLIC_VIEWSETS.items()))
def test_allowlist_entries_still_exist(name, reason):
    """Remove allowlist entries when their viewset goes.

    A stale name is not dangerous on its own, but it makes the list look
    considered when it is really just old, and the next person reads it as
    evidence that everything on it was thought about recently.
    """
    assert name in _api_viewsets(), (
        f"{name} is on PUBLIC_VIEWSETS ({reason}) but no longer exists."
    )
