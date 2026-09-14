__all__ = ["ObservationGroupListView"]

from tom_observations.views import (
    ObservationGroupListView as BaseObservationGroupListView,
)

from goats_tom.views.ordering import DateOrderingMixin


class ObservationGroupListView(DateOrderingMixin, BaseObservationGroupListView):
    """Observation group list, orderable by creation date via ``?order=``."""

    # Keeps TOMToolkit's alphabetical tiebreaker for groups sharing a date.
    tiebreaker = "name"
