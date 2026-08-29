"""Overrides for TOM Toolkit's group views, which bypass object permissions.

A "group" here is a *saved selection* -- `DataProductGroup`, `ObservationGroup`
-- not a group of users. It grants nobody access to anything; it just bundles
items so they can be acted on together.

The problem is that the pages managing those selections do not consistently
check permissions, so they can be used to reach items the viewer has no right
to. Enforcement in TOM is inconsistent per *view*, not per model: the same
`ObservationGroup` is correctly scoped on its own list page and completely
open from the observation list page.

Demonstrated, not theorised: a user with no permissions at all posted another
PI's data product id to the add-to-group endpoint, it was accepted, and the
group page listed the private file by name.

What was wrong, upstream:

- `AddProductToGroupForm.products` is `DataProduct.objects.all()`, so any id
  posted is accepted regardless of who may see it.
- `DataProductGroupListView` is a plain `ListView` -- every group, everyone.
- `DataProductGroupDetailView` is a bare `DetailView`, listing a group's files
  with no permission check and no login requirement.
- `DataProductGroupCreateView` assigns no permissions, unlike its
  `ObservationGroup` and `TargetList` counterparts which assign
  view/change/delete to the creator.
- `DataProductGroupDeleteView` has `LoginRequiredMixin` only, so anyone may
  delete anyone's selection.
- `ObservationListView` adds records to groups via
  `ObservationGroup.objects.filter(id__in=...)`, unfiltered on both sides.

None of this is GOATS-specific and all of it is worth reporting upstream.
"""

__all__ = [
    "GOATSAddProductToGroupView",
    "GOATSDataProductGroupCreateView",
    "GOATSDataProductGroupDeleteView",
    "GOATSDataProductGroupDetailView",
    "GOATSDataProductGroupListView",
    "GOATSObservationListView",
]

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
from tom_dataproducts.models import DataProduct, DataProductGroup
from tom_dataproducts.views import (
    DataProductGroupCreateView,
    DataProductGroupDeleteView,
    DataProductGroupDetailView,
    DataProductGroupDataView,
    DataProductGroupListView,
)
from tom_observations.models import ObservationGroup, ObservationRecord
from tom_observations.views import ObservationListView

from goats_tom.filters import GOATSObservationFilter
from goats_tom.visibility import visible_data_products

logger = logging.getLogger(__name__)

VIEW_DATAPRODUCT = "tom_dataproducts.view_dataproduct"
VIEW_DPGROUP = "tom_dataproducts.view_dataproductgroup"
CHANGE_DPGROUP = "tom_dataproducts.change_dataproductgroup"
DELETE_DPGROUP = "tom_dataproducts.delete_dataproductgroup"
VIEW_OBSERVATION = "tom_observations.view_observationrecord"
CHANGE_OBSGROUP = "tom_observations.change_observationgroup"


def _visible_data_products(user):
    """Data products `user` may view.

    Notes
    -----
    A thin alias over `goats_tom.visibility`, kept because the call sites
    below read better with the short name. The shared module is the single
    definition -- an earlier version of this file had its own copy, and the
    duplicate is how the filter sidebars ended up scoped differently from
    the views beside them.
    """
    return visible_data_products(user)


def _visible_groups(user, model, permission):
    """Selections `user` holds `permission` on."""
    from django.conf import settings  # noqa: PLC0415

    if settings.TARGET_PERMISSIONS_ONLY:
        return model.objects.all()
    return get_objects_for_user(user, permission)


class GOATSDataProductGroupListView(LoginRequiredMixin, DataProductGroupListView):
    """List only the selections the user may view."""

    def get_queryset(self):
        """Restrict to groups the user has permission to see."""
        return _visible_groups(self.request.user, DataProductGroup, VIEW_DPGROUP)


class GOATSDataProductGroupDetailView(
    LoginRequiredMixin, DataProductGroupDetailView
):
    """Show a selection, and only the files in it the user may see.

    Notes
    -----
    Both halves matter. Restricting which *groups* open stops someone
    browsing another PI's selection; restricting the *files listed* stops a
    shared selection leaking members' private data, which is the more subtle
    case -- a legitimately shared group can still contain files that are not.
    """

    def get_queryset(self):
        """Restrict which groups can be opened at all."""
        return _visible_groups(self.request.user, DataProductGroup, VIEW_DPGROUP)

    def get_context_data(self, **kwargs) -> dict:
        """Filter the listed files to those the user may view."""
        context = super().get_context_data(**kwargs)
        visible = _visible_data_products(self.request.user)
        context["object_list"] = self.object.dataproduct_set.filter(
            pk__in=visible.values_list("pk", flat=True)
        )
        return context


class GOATSDataProductGroupCreateView(DataProductGroupCreateView):
    """Create a selection owned by whoever created it.

    Notes
    -----
    Brings data product groups in line with `ObservationGroup` and
    `TargetList`, both of which already assign view/change/delete to their
    creator. Without this a new selection has no permissions at all, which --
    once the list view is scoped -- would make it invisible to the person who
    just made it.
    """

    def form_valid(self, form) -> HttpResponse:
        """Save the group, then grant its creator full control of it."""
        response = super().form_valid(form)
        for action in ("view", "change", "delete"):
            assign_perm(
                f"tom_dataproducts.{action}_dataproductgroup",
                self.request.user,
                self.object,
            )
        return response


class GOATSDataProductGroupDeleteView(DataProductGroupDeleteView):
    """Delete a selection only if the user may delete it."""

    def get_queryset(self):
        """Restrict deletion to groups the user has delete permission on.

        Notes
        -----
        Enforced through the queryset rather than a permission mixin so an
        unauthorised id is a 404 rather than a 403 -- consistent with how the
        rest of GOATS handles objects a user may not see, and it avoids
        confirming that a group exists.
        """
        return _visible_groups(self.request.user, DataProductGroup, DELETE_DPGROUP)


class GOATSAddProductToGroupView(DataProductGroupDataView):
    """Add files to a selection, restricted to what the user may touch."""

    def get_form(self, *args, **kwargs):
        """Offer only files the user may view and groups they may change.

        Notes
        -----
        The form's own querysets are the security boundary here, not the
        rendered checkboxes: `form_valid` resolves whatever ids are posted,
        so narrowing the queryset is what makes an unauthorised id invalid
        rather than merely absent from the page.
        """
        form = super().get_form(*args, **kwargs)
        form.fields["products"].queryset = _visible_data_products(self.request.user)
        form.fields["group"].queryset = _visible_groups(
            self.request.user, DataProductGroup, CHANGE_DPGROUP
        )
        return form


class GOATSObservationListView(ObservationListView):
    """Observation list whose add-to-group action respects permissions.

    Notes
    -----
    Upstream resolves both sides with unfiltered `objects.filter(id__in=...)`,
    so any observation could be added to any group by id -- including groups
    the user cannot see on the group list page, which is exactly the
    inconsistency that makes this hard to notice.

    Scoping the action alone was not enough. The page also *lists* every
    group by name, in the filter sidebar and again in the add/remove bar --
    both of which render the same `{{ filter.form.observationgroup }}` field
    from the FilterSet, not from anything this view controls.
    `GOATSObservationFilter` scopes those choices; the checks below stay
    because the ids in a query string are whatever the caller sent, not
    whatever the dropdown offered.
    """

    filterset_class = GOATSObservationFilter

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle the add/remove action here, then defer to the list itself."""
        selected = request.GET.getlist("selected")
        group_ids = request.GET.getlist("observationgroup")
        action = request.GET.get("action")

        if not (selected and group_ids and action):
            return super().get(request, *args, **kwargs)

        records = get_objects_for_user(request.user, VIEW_OBSERVATION).filter(
            id__in=selected
        )
        groups = _visible_groups(
            request.user, ObservationGroup, CHANGE_OBSGROUP
        ).filter(id__in=group_ids)

        refused = len(selected) - records.count()
        if refused or not groups.exists():
            logger.warning(
                "Refused add-to-group by %s: %d observation(s) and %d group(s) "
                "were not theirs to use.",
                request.user.username,
                refused,
                len(group_ids) - groups.count(),
            )
            messages.error(
                request,
                "Some of those observations or groups are not available to you.",
            )
            return redirect(reverse("tom_observations:list"))

        for group in groups:
            if action == "add":
                group.observation_records.add(*records)
            elif action == "remove":
                group.observation_records.remove(*records)
            group.save()
        return redirect(reverse("tom_observations:list"))
