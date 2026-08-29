"""Scans TOM Toolkit for unscoped querysets handed to templates.

This file exists because the same bug was found four times, by hand, in four
places, and the third and fourth were found by a user looking at a screen
rather than by anything in this repository.

The pattern is always identical. A view scopes what it *returns* and then
hands the template an unscoped queryset for what it *offers*::

    def get_queryset(self):
        return get_objects_for_user(self.request.user,
                                    'tom_dataproducts.view_dataproduct')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['product_groups'] = DataProductGroup.objects.all()
        return context

Both methods are right there, one below the other. Reading the view is not
enough to notice, because the scoped line is what the eye expects to find and
it is genuinely present.

`test_choice_scoping` checks that the *fixes* work -- that the helpers scope
and the forms are narrowed. It cannot find a surface nobody thought of, which
is exactly what was missed twice. So this test does not check behaviour. It
parses TOM's source and fails on the shape, whether or not anyone has thought
about that particular page. Upgrading TOM will re-run it against the new
source and flag any surface the upgrade adds.

Every finding must be listed in `KNOWN_UNSCOPED_CONTEXT` with a GOATS
override that fixes it. A new finding fails the build with the module, line
and context key, which is enough to write the override from.
"""

import ast
import inspect
import re
from pathlib import Path

import pytest
import tom_dataproducts.views
import tom_observations.views
import tom_targets.views

import goats_tom.views
from goats_tom import urls as goats_urls

#: Models whose rows belong to somebody, and so must never be offered whole.
#:
#: `Target` is included even though `targets_for_user` exists, because a view
#: can still reach past it with a plain `objects.all()`.
PERMISSION_BEARING = {
    "DataProduct",
    "DataProductGroup",
    "ObservationGroup",
    "ObservationRecord",
    "ReducedDatum",
    "Target",
    "TargetList",
}

#: Upstream views that hand a template an unscoped queryset, and the GOATS
#: view that overrides each.
#:
#: Keyed by ``module:class:context_key``. Every entry needs an override that
#: actually subclasses the upstream view and is wired into `goats_tom.urls`;
#: both are asserted below, so an entry cannot be silenced by adding a name
#: that does nothing.
KNOWN_UNSCOPED_CONTEXT = {
    "tom_dataproducts.views:DataProductListView:product_groups": (
        "GOATSDataProductListView"
    ),
    "tom_targets.views:TargetListView:groupings": "GOATSTargetListView",
}

SCANNED_MODULES = [
    tom_dataproducts.views,
    tom_observations.views,
    tom_targets.views,
]


def _mentions_unscoped_model(node) -> str | None:
    """Return the model name if `node` contains an unfiltered `objects.all()`.

    Notes
    -----
    Walks the whole expression rather than matching a top-level call, so the
    conditional form upstream uses in `TargetListView` is caught too::

        (TargetList.objects.all() if request.user.is_authenticated
         else TargetList.objects.none())

    Being logged in is not a permission check, so that expression is just as
    unscoped as a bare `objects.all()` -- and reads as though it is not,
    which is presumably why it survived.
    """
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if not isinstance(func, ast.Attribute) or func.attr != "all":
            continue
        manager = func.value
        if not isinstance(manager, ast.Attribute) or manager.attr != "objects":
            continue
        owner = manager.value
        if isinstance(owner, ast.Name) and owner.id in PERMISSION_BEARING:
            return owner.id
    return None


def _findings(module) -> list[tuple[str, str, str, str, int]]:
    """Every ``context[...] = <unscoped queryset>`` in `module`."""
    source = Path(inspect.getfile(module)).read_text()
    tree = ast.parse(source)
    found = []
    for class_node in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for assign in (n for n in ast.walk(class_node) if isinstance(n, ast.Assign)):
            target = assign.targets[0]
            if not isinstance(target, ast.Subscript):
                continue
            if not (isinstance(target.value, ast.Name) and target.value.id == "context"):
                continue
            key = getattr(target.slice, "value", None)
            if not isinstance(key, str):
                continue
            model = _mentions_unscoped_model(assign.value)
            if model:
                found.append(
                    (module.__name__, class_node.name, key, model, assign.lineno)
                )
    return found


@pytest.mark.parametrize("module", SCANNED_MODULES, ids=lambda m: m.__name__)
def test_no_unknown_unscoped_context(module):
    """Every unscoped context queryset is known and overridden.

    Notes
    -----
    A failure here is not necessarily a vulnerability -- it is a surface
    nobody has looked at yet. Decide whether it leaks, then either write the
    override or add the entry with a reason.
    """
    for module_name, class_name, key, model, lineno in _findings(module):
        identifier = f"{module_name}:{class_name}:{key}"
        assert identifier in KNOWN_UNSCOPED_CONTEXT, (
            f"{module_name}:{lineno} -- {class_name}.get_context_data assigns "
            f"context[{key!r}] = {model}.objects.all(), which offers every "
            f"user's {model} to whoever loads the page. Write a GOATS "
            f"override scoping it (see goats_tom.views.dataproduct_list) and "
            f"add it to KNOWN_UNSCOPED_CONTEXT."
        )


@pytest.mark.parametrize(
    ("identifier", "override_name"), sorted(KNOWN_UNSCOPED_CONTEXT.items())
)
def test_known_findings_have_a_real_override(identifier, override_name):
    """Each listed override exists and subclasses the view it replaces.

    Notes
    -----
    Guards against the allowlist becoming a place to put names. An entry
    naming a class that does not exist, or one that does not actually
    replace the upstream view, would otherwise silence the scan while
    fixing nothing.
    """
    module_name, class_name, _ = identifier.split(":")
    override = getattr(goats_tom.views, override_name, None)
    assert override is not None, f"{override_name} is not exported from goats_tom.views"

    upstream_module = {m.__name__: m for m in SCANNED_MODULES}[module_name]
    upstream = getattr(upstream_module, class_name)
    assert issubclass(override, upstream), (
        f"{override_name} does not subclass {class_name}, so it does not "
        "replace it."
    )


@pytest.mark.parametrize("override_name", sorted(set(KNOWN_UNSCOPED_CONTEXT.values())))
def test_overrides_are_wired_into_urls(override_name):
    """Each override is routed, ahead of the tom_* include that it shadows.

    Notes
    -----
    An override that is written, exported and never routed is the failure
    mode this catches: the class looks like a fix in review and the
    upstream view keeps serving the page. Checked against the URL module's
    source rather than the resolver, because these paths shadow the
    `tom_*` includes by declaration order and the assertion should be about
    that ordering.
    """
    source = Path(inspect.getfile(goats_urls)).read_text()
    assert re.search(rf"\b{override_name}\.as_view\(\)", source), (
        f"{override_name} is never routed in goats_tom.urls, so the "
        "unscoped upstream view still serves the page."
    )
