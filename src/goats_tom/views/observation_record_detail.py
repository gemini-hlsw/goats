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
from goats_tom.visibility import (
    changeable_data_product_groups,
    shareable_users,
    visible_data_products,
)

logger = logging.getLogger(__name__)


def _scoped_add_product_form(user) -> AddProductToGroupForm:
    """An `AddProductToGroupForm` offering only what `user` may touch.

    Notes
    -----
    Files are limited to those the user may view and groups to those they
    may change: adding to a selection modifies it, so view alone is not
    enough to be offered it as a destination.
    """
    form = AddProductToGroupForm()
    form.fields["products"].queryset = visible_data_products(user)
    form.fields["group"].queryset = changeable_data_product_groups(user)
    return form


class ObservationRecordDetailView(BaseObservationRecordDetailView):
    """View to override creating thumbnails."""

    def get_context_data(self, *args, **kwargs):
        """Override for avoiding "get_preview" and creating thumbnail."""
        context = super(DetailView, self).get_context_data(*args, **kwargs)
        # The "add to data product group" form. Upstream builds it from
        # `DataProduct.objects.all()` and `DataProductGroup.objects.all()`,
        # so it named every PI's selections here even though the group list
        # page and the add endpoint were both scoped. The form's querysets
        # are also its validators, so narrowing them is what makes a posted
        # id from another PI's group invalid rather than merely absent from
        # the page.
        context["form"] = _scoped_add_product_form(self.request.user)
        facility = tom_observations_get_service_class(self.object.facility)()
        facility.set_user(self.request.user)
        observation_record = self.get_object()

        # Sharing and read-only mode.
        #
        # `can_share_observation` gates the share modal; `can_edit_observation`
        # gates every control that changes something -- the GOA query form,
        # the DRAGONS panel, add-to-group, the observation id form and
        # cancellation. Both are `change` on the record, but they are kept
        # as separate names because they answer different questions and
        # will not necessarily stay equal.
        #
        # A recipient of a read-only share still reaches this page: seeing
        # an observation and its data is the point of sharing, and hiding
        # the page would make the share useless. What they lose is the
        # ability to act on it.
        #
        # These decide what is *rendered*. Each underlying view re-checks
        # for itself, since a hidden form is not an access check -- see
        # `GOAQueryFormView`.
        can_change = self.request.user.is_superuser or self.request.user.has_perm(
            "tom_observations.change_observationrecord", observation_record
        )
        context["can_share_observation"] = can_change
        context["can_edit_observation"] = can_change
        context["shareable_groups"] = self.request.user.groups.all()
        context["shareable_users"] = shareable_users(self.request.user)

        # Editable also requires change: it drives the observation id form,
        # which is a write.
        context["editable"] = (
            isinstance(facility, BaseManualObservationFacility) and can_change
        )
        # Filtered by view permission. `all_data_products` resolves files
        # straight from the observation record with no permission check, so
        # unfiltered it hands every file on the observation to anyone who
        # can load the page -- including the download links in the table and
        # the hidden add-to-group inputs, which read from this same list.
        all_products = facility.all_data_products(self.object)
        context["data_products"] = {
            "saved": [
                product
                for product in all_products.get("saved", [])
                if self.request.user.has_perm(
                    "tom_dataproducts.view_dataproduct", product
                )
            ],
            "unsaved": all_products.get("unsaved", []),
        }
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
