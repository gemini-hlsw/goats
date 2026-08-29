"""Target list filtering scoped to what the requesting user may see.

`tom_targets.filters.TargetFilterSet` builds its "Target Group" dropdown from
a queryset that checks only whether somebody is logged in::

    def get_target_list_queryset(request):
        if request.user.is_authenticated:
            return TargetList.objects.all()
        else:
            return TargetList.objects.none()

So every PI's target groups are named to every other PI in the advanced
filter panel of the target list.

The action behind it was never open: `TargetAddRemoveGroupingView` checks
`view_targetlist` on the grouping before adding or removing anything. This is
the same shape as the observation group bug -- enforcement correct, display
leaking -- which is why fixing the action alone left the names on screen.

The dropdown on the target list page itself is a separate surface, built from
``context['groupings']`` rather than from this FilterSet; it is fixed in
`goats_tom.views.target_list`. Two surfaces, one leak, and finding only one
of them is how this survived the last pass.
"""

__all__ = ["GOATSTargetFilterSet"]

import django_filters
from django import forms
from tom_targets.filters import TargetFilterSet

from goats_tom.visibility import visible_target_lists


class GOATSTargetFilterSet(TargetFilterSet):
    """`TargetFilterSet` whose target group choices are scoped to the user.

    Notes
    -----
    The field is redeclared rather than patched in `__init__` because
    `TargetFilterSet` caches its form in a `form` property, so a queryset
    assigned after the form is first built would not reach the widget.
    A callable queryset is resolved when the field is constructed, which is
    late enough to see the request.

    The widget attributes are reproduced verbatim from upstream. They are
    HTMX bindings that drive the table refresh, and dropping them would
    leave a filter that renders but does nothing.
    """

    targetlist__name = django_filters.ModelChoiceFilter(
        queryset=visible_target_lists,
        label="Target Group",
        widget=forms.Select(
            attrs={
                "hx-get": "",
                "hx-trigger": "change",
                "hx-target": "div.table-container",
                "hx-swap": "innerHTML",
                "hx-indicator": ".progress",
                "hx-include": "closest form",
            }
        ),
    )
