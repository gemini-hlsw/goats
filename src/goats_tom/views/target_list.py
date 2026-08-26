__all__ = ["TargetListView"]

from tom_targets.views import TargetListView as BaseTargetListView

from goats_tom.views.ordering import DateOrderingMixin


class TargetListView(DateOrderingMixin, BaseTargetListView):
    """Target list, orderable by creation date via ``?order=``."""
