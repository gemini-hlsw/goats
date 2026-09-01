__all__ = ["ObservationRecordDeleteView"]
from django.core.exceptions import PermissionDenied
from django.forms import Form
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.urls import reverse_lazy
from django.views.generic import DeleteView
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.permissions import undeletable_dataproducts
from goats_tom.utils import delete_associated_data_products


class ObservationRecordDeleteView(Raise403PermissionRequiredMixin, DeleteView):
    """View for deleting an observation."""

    permission_required = "tom_observations.delete_observationrecord"
    success_url = reverse_lazy("observations:list")
    model = ObservationRecord

    def check_permissions(self, request: HttpRequest):
        """Require delete on the record *and* on every file it would take.

        Parameters
        ----------
        request : `HttpRequest`
            The request whose user is being checked.

        Returns
        -------
        Falsy when the request may proceed, following guardian's inverted
        convention for this method.

        Notes
        -----
        This was a way around the delete guardrail rather than a hole in it.
        `form_valid` calls `delete_associated_data_products`, so deleting an
        observation destroys every file on it -- but the only permission
        checked was `delete_observationrecord`, through `has_perm`, which
        returns `True` for any superuser before guardian is consulted. An
        administrator refused at the Delete and Delete All buttons could
        still destroy the same files with one click here.

        A guardrail with a door beside it is not a guardrail. The check that
        governs the data products has to hold wherever the data products
        actually go, so this asks the same question
        `DeleteObservationDataProductsView` asks, in addition to the
        record's own permission.
        """
        response = super().check_permissions(request)
        if response:
            return response

        refused = undeletable_dataproducts(
            request.user,
            DataProduct.objects.filter(observation_record=self.get_object()),
        )
        if refused:
            raise PermissionDenied(
                "You do not have permission to delete every data product on "
                "this observation, and deleting the observation would "
                "destroy them."
            )
        return None

    def form_valid(self, form: Form) -> HttpResponse:
        """Handle deletion of associated DataProducts upon valid form
        submission.

        Parameters
        ----------
        form : `Form`
            The form object.

        Returns
        -------
        `HttpResponse`
            HTTP response indicating the outcome of the deletion process.

        """
        # Fetch the ObservationRecord object.
        observation_record = self.get_object()
        delete_associated_data_products(observation_record)

        return super().form_valid(form)
