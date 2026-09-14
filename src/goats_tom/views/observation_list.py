__all__ = ["ObservationListView"]

from tom_observations.views import ObservationListView as BaseObservationListView

from goats_tom.views.ordering import DateOrderingMixin


class ObservationListView(DateOrderingMixin, BaseObservationListView):
    """Observation list, orderable by creation date via ``?order=``."""

    # Observations submitted together share a timestamp, so fall back to their id.
    tiebreaker = "observation_id"

    def get_filterset_kwargs(self, filterset_class):
        """Give the header's explicit order precedence over the form's ordering."""
        kwargs = super().get_filterset_kwargs(filterset_class)
        if "order" in self.request.GET:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"].pop("ordering", None)
        return kwargs

    def get_context_data(self, **kwargs):
        """Reflect the form's ordering when no header order was requested."""
        context = super().get_context_data(**kwargs)
        if "order" not in self.request.GET and self.filterset.is_bound:
            form = self.filterset.form
            ordering = getattr(form, "cleaned_data", {}).get("ordering")
            if ordering:
                context["current_order"] = ordering[0]
        return context
