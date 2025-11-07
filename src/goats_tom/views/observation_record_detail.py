__all__ = ["ObservationRecordDetailView"]
import logging
import re
from typing import Any

from django.urls import reverse
from django.views.generic import DetailView
from tom_dataproducts.forms import AddProductToGroupForm, DataProductUploadForm
from tom_observations.facility import BaseManualObservationFacility
from tom_observations.facility import (
    get_service_class as tom_observations_get_service_class,
)
from tom_observations.views import (
    ObservationRecordDetailView as BaseObservationRecordDetailView,
)

logger = logging.getLogger(__name__)


def _is_gpp_id(obs_id: str) -> bool:
    """
    Return True if the observation ID is a GPP-style ID, otherwise False.

    Parameters
    ----------
    obs_id : str
        The observation ID to check.

    Returns
    -------
    bool
        True if it is a GPP ID (e.g., G-2026A-0166-Q-0001), False otherwise.
    """
    pattern = re.compile(r"^G-(?![NS]-)")
    return bool(pattern.match(obs_id))


class ObservationRecordDetailView(BaseObservationRecordDetailView):
    """View to override creating thumbnails."""

    def get_context_data(self, *args, **kwargs):
        """Override for avoiding "get_preview" and creating thumbnail."""
        context = super(DetailView, self).get_context_data(*args, **kwargs)
        context["form"] = AddProductToGroupForm()
        facility = tom_observations_get_service_class(self.object.facility)()
        facility.set_user(self.request.user)
        observation_record = self.get_object()

        context["editable"] = isinstance(facility, BaseManualObservationFacility)
        context["data_products"] = facility.all_data_products(self.object)
        context["can_be_cancelled"] = (
            self.object.status not in facility.get_terminal_observing_states()
        )
        context["target"] = observation_record.target
        data_product_upload_form = DataProductUploadForm(
            initial={
                "observation_record": observation_record,
                "referrer": reverse(
                    "tom_observations:detail",
                    args=(self.get_object().id,),
                ),
            },
        )
        context["data_product_form"] = data_product_upload_form
        context["observation_id"] = observation_record.observation_id
        # Add GPP URL if applicable
        context["gpp_url"] = self._get_gpp_url(observation_record)
        return context

    @staticmethod
    def _get_gpp_url(observation_record: Any) -> str | None:
        """Return the Explore URL if this is a GPP Gemini observation."""
        if (
            not _is_gpp_id(observation_record.observation_id)
            or observation_record.facility != "GEM"
        ):
            return None

        try:
            program_id = observation_record.parameters.get("gpp_program_id")
            obs_id = observation_record.parameters.get("gpp_id")
            if program_id and obs_id:
                return f"https://explore.gemini.edu/{program_id}/observation/{obs_id}"
        except Exception:
            logger.exception(
                "Failed to build GPP URL for observation %s",
                observation_record.observation_id,
            )
        return None
