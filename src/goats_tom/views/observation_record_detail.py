__all__ = ["ObservationRecordDetailView"]
import logging

from django.conf import settings
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

from goats_tom.utils import is_gpp_id

logger = logging.getLogger(__name__)


class ObservationRecordDetailView(BaseObservationRecordDetailView):
    """View to override creating thumbnails."""

    def get_context_data(self, *args, **kwargs):
        """Override for avoiding "get_preview" and creating thumbnail."""
        context = super(DetailView, self).get_context_data(*args, **kwargs)
        context["form"] = AddProductToGroupForm()
        facility = tom_observations_get_service_class(self.object.facility)()
        facility.set_user(self.request.user)
        observation_record = self.get_object()

        # Sharing controls for the observation and its data products.
        #
        # Both templates need the same two values, so they are worked out
        # once here rather than in each. `shareable_groups` is the user's own
        # groups: the select element must not offer a collaboration they have
        # nothing to do with, and the view re-checks it besides, since a
        # select element is not a security boundary.
        context["can_share_observation"] = (
            self.request.user.is_superuser
            or self.request.user.has_perm(
                "tom_observations.change_observationrecord", observation_record
            )
        )
        context["shareable_groups"] = self.request.user.groups.all()

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
            not is_gpp_id(observation_record.observation_id)
            or observation_record.facility != "GEM"
        ):
            return None

        try:
            program_id = observation_record.parameters.get("gpp_program_id")
            obs_id = observation_record.parameters.get("gpp_id")
            if program_id and obs_id:
                # Follows GPP_ENV, matching the navbar link: an
                # observation submitted to the development ODB has no page in
                # production Explore.
                base = settings.GPP_EXPLORE_URL.rstrip("/")
                return f"{base}/{program_id}/observation/{obs_id}"
            else:
                raise KeyError("Missing gpp_program_id or gpp_id in parameters")
        except Exception as exc:
            logger.exception(
                "Failed to build GPP URL for observation %s: %s",
                observation_record.observation_id,
                exc,
            )
        return None
