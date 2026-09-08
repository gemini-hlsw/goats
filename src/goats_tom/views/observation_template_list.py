__all__ = ["ObservationTemplateListView"]

from tom_observations.views import (
    ObservationTemplateListView as BaseObservationTemplateListView,
)

from goats_tom.views.ordering import DateOrderingMixin


class ObservationTemplateListView(DateOrderingMixin, BaseObservationTemplateListView):
    """Observation template list, orderable by creation date via ``?order=``."""
