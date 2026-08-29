"""Observation list filtering scoped to what the requesting user may see.

Upstream's `tom_observations.views.ObservationFilter` builds its choice
fields from unfiltered querysets::

    observationgroup = ModelMultipleChoiceFilter(
        label='Observation Groups', queryset=ObservationGroup.objects.all()
    )
    target_id = ModelMultipleChoiceFilter(
        queryset=Target.objects.filter(observationrecord__isnull=False)...
    )

That is correct on a desktop install, where the only person who can log in
owns every row. On a shared server it lists every PI's observation groups
and every PI's target names to everyone.

The *records* were never the leak -- `ObservationListView.get_queryset`
scopes those with `get_objects_for_user`. What leaks is the **choices in the
form**, which is why the group list page could correctly hide a group while
the observation list page showed its name in a dropdown.

One filter, two places on the page
----------------------------------
`observation_list.html` renders ``{{ filter.form.observationgroup }}`` twice:
once in the filter sidebar, and once in the add/remove bar above the table::

    <button type="submit" name="action" value="add" ...>Add</button>
    <button type="submit" name="action" value="remove" ...>Remove</button>
    Selected observations from group
    {{ filter.form.observationgroup }}

Both widgets are the same bound field of the same FilterSet, so scoping the
queryset here fixes both at once -- and conversely, scoping only the action
handler in `GOATSObservationListView` left both dropdowns still populated,
which is what was reported on the live instance.

This is presentation, not enforcement. `GOATSObservationListView` still
re-checks permissions on the ids that come back, because a dropdown is a
suggestion and a query parameter is whatever the caller typed.
"""

__all__ = ["GOATSObservationFilter"]

from django.conf import settings
from django_filters import ModelMultipleChoiceFilter
from tom_observations.views import ObservationFilter
from tom_targets.models import Target

from goats_tom.visibility import (
    visible_observation_groups,
    visible_observation_records,
)


def _visible_observed_targets(request):
    """Targets with observations that the requesting user may view.

    Notes
    -----
    Scoped through the observation records rather than through the targets:
    the dropdown exists to filter *this user's* observation list, so a target
    they can see but have no observations on is noise, and a target they
    cannot see should not be named at all.

    `visible_targets` is deliberately not used here for that reason -- it
    answers a different question ("which targets may I see?") than the one
    this dropdown asks ("which targets appear in my observation list?").
    """
    observed = Target.objects.filter(observationrecord__isnull=False)
    if settings.TARGET_PERMISSIONS_ONLY:
        return observed.distinct().order_by("name")
    return (
        observed.filter(observationrecord__in=visible_observation_records(request))
        .distinct()
        .order_by("name")
    )


class GOATSObservationFilter(ObservationFilter):
    """`ObservationFilter` whose choice fields list only what the user may see.

    Notes
    -----
    The querysets are callables rather than querysets. `django_filters`
    supports this directly through `QuerySetRequestMixin`: a callable
    ``queryset`` is invoked with the request when the field is built, which
    is the documented way to scope choices by the logged-in user. It is
    preferable to overriding `__init__`, since the field is constructed
    lazily and a queryset fixed at instance-creation time can be built
    before the request is attached.
    """

    observationgroup = ModelMultipleChoiceFilter(
        label="Observation Groups", queryset=visible_observation_groups
    )
    target_id = ModelMultipleChoiceFilter(queryset=_visible_observed_targets)
