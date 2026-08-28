"""Adding an existing observation, with permissions assigned.

Overrides `tom_observations.views.AddExistingObservationView`, whose
`form_valid` creates the record with a bare
``ObservationRecord.objects.create`` and assigns no per-object permissions.

Under ``TARGET_PERMISSIONS_ONLY = False`` that produced a silent failure: the
form reported success, the record was written, and it appeared in nobody's
observation list -- not even the creator's. Nothing errored, which made it
look like the save had simply not happened.
"""

__all__ = ["GOATSAddExistingObservationView"]

import logging

from django.http import HttpResponse
from tom_observations.models import ObservationRecord
from tom_observations.views import AddExistingObservationView

from goats_tom.permissions import grant_observation_permissions

logger = logging.getLogger(__name__)


class GOATSAddExistingObservationView(AddExistingObservationView):
    """Add an existing observation and grant its creator access to it."""

    def form_valid(self, form) -> HttpResponse:
        """Create the record upstream, then assign permissions to the user.

        Notes
        -----
        The record is looked up after the fact rather than by wrapping the
        creation: upstream's `form_valid` decides between creating a record
        and redirecting for confirmation when a duplicate exists, and
        reproducing that logic here would mean maintaining a copy of it.
        Fetching the newest matching record afterwards leaves that decision
        upstream where it belongs.

        A missing record is not an error here -- it means upstream chose to
        redirect for confirmation rather than create anything.
        """
        response = super().form_valid(form)

        record = (
            ObservationRecord.objects.filter(
                target_id=form.cleaned_data["target_id"],
                facility=form.cleaned_data["facility"],
                observation_id=form.cleaned_data["observation_id"],
            )
            .order_by("-created")
            .first()
        )
        if record is not None:
            grant_observation_permissions(record, self.request.user)
        return response
