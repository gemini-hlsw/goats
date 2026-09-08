__all__ = ["BrokerQueryListView"]

from tom_alerts.views import BrokerQueryListView as BaseBrokerQueryListView

from goats_tom.views.ordering import DateOrderingMixin


class BrokerQueryListView(DateOrderingMixin, BaseBrokerQueryListView):
    """Saved query list, orderable by creation or last run date via ``?order=``."""

    orderable_fields = ("created", "last_run")
