__all__ = ["DRAGONSView"]

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.generic import View
from tom_observations.models import ObservationRecord

from goats_tom.permissions import may_reduce_observation


class DRAGONSView(LoginRequiredMixin, View):
    """A Django view for displaying the DRAGONS page.

    Notes
    -----
    Requires full access to the observation -- `may_reduce_observation` --
    for the same reason the DRAGONS panel is hidden from a read-only
    recipient on the observation detail page. Refusals reach the Access
    Denied page through `PermissionDeniedMiddleware` rather than the login
    form.
    """

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handles GET requests to display DRAGONS.

        Parameters
        ----------
        request : `HttpRequest`
            The request object.
        pk : `int`
            The primary key of the `ObservationRecord`.

        Returns
        -------
        `HttpResponse`
            The rendered DRAGONS page.

        """
        observation_record = get_object_or_404(ObservationRecord, pk=pk)

        # `LoginRequiredMixin` alone let any authenticated user open any
        # PI's reduction page by guessing a pk, and every control on it
        # POSTs to endpoints keyed on this record. The observation detail
        # page hides the DRAGONS panel from a read-only recipient via
        # `can_edit_observation`, and its own comment says the underlying
        # views re-check for themselves -- which was true of
        # `GOAQueryFormView` beside it and not of this one.
        if not may_reduce_observation(request.user, observation_record):
            raise PermissionDenied(
                "You do not have permission to reduce this observation."
            )

        dragons_runs = observation_record.dragons_runs.all()

        # Get the available folders for display.
        return render(
            request,
            "dragons_index.html",
            {"observation_record": observation_record, "dragons_runs": dragons_runs},
        )
