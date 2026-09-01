"""Guards that every API endpoint which can destroy data checks the object.

`test_api_scoping` asks whether a viewset restricts what it *returns*. That is
a different question from whether it restricts what it lets you *destroy*, and
the gap between the two is where the superuser delete ban failed: both delete
*views* were fixed and verified, while `DELETE /api/dataproducts/<pk>/` went on
performing no permission check at all, because GOATS sets
``DEFAULT_PERMISSION_CLASSES`` to an empty list and upstream's viewset declares
only ``view_dataproduct``.

Read scoping did not catch it, and could not: the endpoint was correctly scoped
for reading. You could only delete what you could see -- which, for a superuser,
is everything.

So this file asks the second question on every run.
"""

import pytest
from django.urls import get_resolver, resolve
from rest_framework.mixins import DestroyModelMixin

from goats_tom.api_views import GOATSDataProductViewSet
from goats_tom.permissions import AssignedObjectPermissions

#: Viewsets that expose a destructive method without an object-level
#: permission class, on purpose.
#:
#: Each entry needs a reason. An endpoint that can delete somebody else's data
#: does not belong here without one.
UNCHECKED_DESTRUCTIVE_VIEWSETS: dict[str, str] = {}


def _api_viewsets():
    """Yield every GOATS viewset class reachable from the URL configuration."""
    seen = {}
    patterns = list(get_resolver().url_patterns)
    while patterns:
        pattern = patterns.pop()
        nested = getattr(pattern, "url_patterns", None)
        if nested is not None:
            patterns.extend(nested)
            continue
        callback = getattr(pattern, "callback", None)
        cls = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        if cls is not None and cls.__module__.startswith("goats_tom"):
            seen[cls.__name__] = cls
    return seen


def _is_destructive(cls) -> bool:
    """Whether the viewset exposes a method that can destroy or overwrite data."""
    if issubclass(cls, DestroyModelMixin):
        allowed = getattr(cls, "http_method_names", None)
        # A viewset that inherits the mixin but does not route DELETE cannot
        # be reached destructively -- `DataProductTypeViewSet` narrows itself
        # this way.
        if allowed is not None and "delete" not in [m.lower() for m in allowed]:
            return False
        return True
    return False


def test_destructive_endpoints_check_the_object():
    """A viewset that can delete must consult the assigned permission rows.

    Notes
    -----
    `AssignedObjectPermissions` specifically, not merely *some* permission
    class. `permissions.IsAuthenticated` would pass a naive check and stop
    nothing, and DRF's own `DjangoObjectPermissions` goes through
    `ModelBackend`, which returns `True` for any superuser before guardian is
    consulted -- so it would reinstate exactly the bypass this work removes.
    """
    unchecked = []
    for name, cls in sorted(_api_viewsets().items()):
        if name in UNCHECKED_DESTRUCTIVE_VIEWSETS:
            continue
        if not _is_destructive(cls):
            continue
        classes = getattr(cls, "permission_classes", None) or []
        if any(
            isinstance(permission, type)
            and issubclass(permission, AssignedObjectPermissions)
            for permission in classes
        ):
            continue
        unchecked.append(name)

    assert not unchecked, (
        "These GOATS API viewsets can destroy data without checking the "
        f"object's assigned permissions: {unchecked}. Add a subclass of "
        "`AssignedObjectPermissions` to `permission_classes`, remove DELETE "
        "from `http_method_names`, or add the name to "
        "UNCHECKED_DESTRUCTIVE_VIEWSETS with a reason."
    )


def test_dataproducts_api_route_belongs_to_goats():
    """`/api/dataproducts/<pk>/` must resolve to the GOATS viewset.

    Notes
    -----
    The override works by claiming the ``dataproducts`` basename on
    `SharedAPIRootRouter` before `tom_dataproducts.urls` can, which depends on
    `goats_tom.urls` being imported first. That is true today and is not
    guaranteed by anything a reader of either file would notice.

    This is the same question that had to be asked of
    `GOATSObservationListView`, and it is worth a test rather than a comment:
    every fix in this work that was verified only against the permission
    primitive has held, and every one that depended on view resolution has
    not.
    """
    match = resolve("/api/dataproducts/1/")
    cls = getattr(match.func, "cls", None)
    assert cls is GOATSDataProductViewSet, (
        "/api/dataproducts/<pk>/ resolves to "
        f"{cls.__module__}.{cls.__name__} rather than GOATSDataProductViewSet. "
        "Upstream's viewset exposes DELETE with no object-level permission "
        "check; if it is serving this route, the delete guardrail is absent."
    )


@pytest.mark.parametrize(
    "name,reason", sorted(UNCHECKED_DESTRUCTIVE_VIEWSETS.items())
)
def test_allowlist_entries_still_exist(name, reason):
    """Remove allowlist entries when their viewset goes.

    A stale name makes the list look considered when it is only old.
    """
    assert name in _api_viewsets(), (
        f"{name} is on UNCHECKED_DESTRUCTIVE_VIEWSETS ({reason}) but no "
        "longer exists."
    )


#: Views that destroy data products as a *side effect* of deleting something
#: else, and so have to carry the same guardrail as the delete buttons.
#:
#: This is where the ban leaked in practice. `DataProductDeleteView` and
#: `DeleteObservationDataProductsView` were the two views anybody thought to
#: fix, because they are the two whose names say "delete data product".
#: Deleting an observation, or a target, destroys the same files through
#: `delete_associated_data_products` while checking only
#: `delete_observationrecord` or `delete_target` -- both of which go through
#: `has_perm` and are therefore already a superuser bypass.
CASCADING_DELETE_VIEWS = (
    "goats_tom.views.observation_record_delete",
    "goats_tom.views.target_delete",
    "goats_tom.views.delete_observation_dataproducts",
    "goats_tom.views.dataproduct_delete",
)


@pytest.mark.parametrize("module_name", CASCADING_DELETE_VIEWS)
def test_cascading_deletes_consult_the_guardrail(module_name):
    """Anything that destroys files must ask the shared permission helper.

    Notes
    -----
    A structural check, not a behavioural one, and worth saying so: it
    asserts the call is present, not that it is correct. It exists because
    the failure being guarded against is *omission* -- a new cascade added
    without anyone remembering the guardrail -- which no amount of testing
    the two views people do remember would catch.

    The behavioural test belongs with a live request and cannot run until the
    suite runs somewhere DRAGONS is installed.
    """
    import importlib
    import inspect

    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    assert "undeletable_dataproducts" in source, (
        f"{module_name} destroys data products without consulting "
        "`goats_tom.permissions.undeletable_dataproducts`. Sharing grants "
        "view and, at full access, change -- never delete -- and a superuser "
        "bypasses `has_perm` entirely, so a cascade that checks only its own "
        "model's permission is a way around the guardrail rather than a hole "
        "in it."
    )


#: Views that delete a saved selection -- a `TargetList`, `ObservationGroup`
#: or `DataProductGroup`.
#:
#: Upstream leaks all three differently: two check with `has_perm`, and the
#: third scopes with `get_objects_for_user`, whose `with_superuser` argument
#: defaults to True. Both are a superuser bypass; only one of them looks like
#: one.
SELECTION_DELETE_VIEWS = (
    "GOATSTargetGroupingDeleteView",
    "GOATSObservationGroupDeleteView",
    "GOATSDataProductGroupDeleteView",
)


@pytest.mark.parametrize("view_name", SELECTION_DELETE_VIEWS)
def test_selection_deletes_exclude_superusers(view_name):
    """Deleting somebody's saved selection must not be a superuser power."""
    import inspect

    from goats_tom.views import groups

    view = getattr(groups, view_name)
    source = inspect.getsource(view.get_queryset)
    assert "with_superuser=False" in source, (
        f"{view_name} scopes deletion with `get_objects_for_user`'s default "
        "`with_superuser=True`, which hands every PI's saved selections to "
        "any administrator. Pass `with_superuser=False`."
    )


def test_target_delete_asks_the_target_rule():
    """Target deletion must be decided by the target, not only by its files."""
    import inspect

    from goats_tom.views import target_delete

    source = inspect.getsource(target_delete)
    assert "may_delete_target" in source, (
        "TargetDeleteView does not consult "
        "`goats_tom.permissions.may_delete_target`. Upstream scopes this "
        "view with `targets_for_user(..., 'delete_target')`, which returns "
        "everything to a superuser, so without it there is no target-level "
        "check at all."
    )
