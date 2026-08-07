__all__ = ["TargetDeleteView"]
from django.contrib import messages
from django.forms import Form
from django.http import (
    HttpResponse,
)
from django.shortcuts import redirect
from tom_observations.models import ObservationRecord
from tom_targets.views import TargetDeleteView as BaseTargetDeleteView

from goats_tom.antares_target_save import target_saver_usernames
from goats_tom.utils import delete_associated_data_products


class TargetDeleteView(BaseTargetDeleteView):
    def form_valid(self, form: Form) -> HttpResponse:
        """Handle deletion of associated observation records upon valid form
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
        target = self.get_object()

        # Checked before anything is torn down. A shared target is refused by
        # `goats_tom.signals.block_shared_target_deletion` as a backstop, but
        # that fires at delete time -- by which point the loop below has
        # already destroyed the observation records. Refusing here keeps them.
        savers = target_saver_usernames(target)
        if len(savers) > 1:
            messages.error(
                self.request,
                f"{target.name} is shared by {len(savers)} teams "
                f"({', '.join(savers)}) and cannot be deleted. Deleting it "
                f"would remove it from all of them.",
            )
            return redirect(target.get_absolute_url())

        # Fetch the ObservationRecord object.
        observation_records = ObservationRecord.objects.filter(target=target)
        for observation_record in observation_records:
            # Delete the observation data products.
            delete_associated_data_products(observation_record)
            # Delete the observation record itself.
            observation_record.delete()

        # Proceed with deletion of the object.
        return super().form_valid(form)
