"""Target list view whose grouping dropdown lists only the user's own groups.

`tom_targets.views.TargetListView.get_context_data` populates the
"Add/Remove from grouping" select with::

    context['groupings'] = (TargetList.objects.all()
                            if self.request.user.is_authenticated
                            else TargetList.objects.none())

Being logged in is the whole check, so the select names every PI's target
groups. `target_list.html` renders it directly::

    <select name="grouping" ...>
      {% for grouping in groupings %}
      <option value="{{ grouping.id }}">{{ grouping.name }}</option>

Nothing is granted by this -- `TargetAddRemoveGroupingView` checks
`view_targetlist` on the posted id and refuses -- so the leak is disclosure
rather than access. On an instance holding proprietary data, the existence
and naming of another team's work is itself worth protecting.

The filter sidebar on the same page leaks the same names through a different
queryset; see `goats_tom.filters.target`.
"""

__all__ = ["GOATSTargetListView"]

from tom_targets.views import TargetListView

from goats_tom.filters.target import GOATSTargetFilterSet
from goats_tom.visibility import visible_target_lists


class GOATSTargetListView(TargetListView):
    """Target list whose grouping select and filter are scoped to the user."""

    filterset_class = GOATSTargetFilterSet

    def get_context_data(self, *args, **kwargs):
        """Replace the unscoped grouping list with the user's own.

        Notes
        -----
        Overridden after calling `super`, rather than reimplemented, so
        everything else the upstream method assembles -- the skymap objects,
        the target count, the query string -- keeps working and keeps
        tracking upstream changes.
        """
        context = super().get_context_data(*args, **kwargs)
        context["groupings"] = visible_target_lists(self.request.user)
        return context
