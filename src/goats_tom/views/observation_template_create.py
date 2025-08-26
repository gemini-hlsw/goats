__all__ = ["ObservationTemplateCreateView"]

import logging

from tom_observations.facility import (
    get_service_class,
)
from tom_observations.views import (
    ObservationTemplateCreateView as BaseObservationTemplateCreateView,
)

logger = logging.getLogger(__name__)


class ObservationTemplateCreateView(BaseObservationTemplateCreateView):
    """
    Overrides the tomtoolkit method to provide the user to the facility settings.
    """

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        facility = get_service_class(self.get_facility_name())()
        facility.set_user(self.request.user)
        try:
            context["missing_configurations"] = ", ".join(
                facility.facility_settings.get_unconfigured_settings()
            )
        except AttributeError:
            context["missing_configurations"] = ""
        return context
