"""
Observation creation view override to provide user to facility settings.
"""

__all__ = ["ObservationCreateView"]

import logging

from tom_observations.views import ObservationCreateView as BaseObservationCreateView
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class ObservationCreateView(BaseObservationCreateView):
    """
    Overrides the tomtoolkit method to provide the user to the facility settings.
    """

    def get_context_data(self, *args, **kwargs):
        """
        Get the context data for the observation creation view. This is an override
        of the tomtoolkit method to provide the user to the facility settings and
        to populate initial form data.
        """
        context = super(ObservationCreateView, self).get_context_data(**kwargs)

        # Populate initial values for each form and add them to the context. If the page
        # reloaded due to form errors, only repopulate the form that was submitted.
        observation_type_choices = []
        initial = self.get_initial()
        facility = self.get_facility_class()()
        facility.set_user(self.request.user)
        observation_form_classes = facility.get_form_classes_for_display(**kwargs)
        for (
            observation_type,
            observation_form_class,
        ) in observation_form_classes.items():
            form_data = {**initial, **{"observation_type": observation_type}}
            # Repopulate the appropriate form with form data if the original submission
            # was invalid
            if observation_type == self.request.POST.get("observation_type"):
                form_data.update(**self.request.POST.dict())

            observation_form_class = type(  # noqa: PLW2901
                f"Composite{observation_type}Form",
                (self.get_cadence_strategy_form(), observation_form_class),
                {},
            )
            observation_type_choices.append(
                (
                    observation_type,
                    observation_form_class(
                        initial=form_data, facility_settings=facility.facility_settings
                    ),
                )
            )
        context["observation_type_choices"] = observation_type_choices

        # Ensure correct tab is active if submission is unsuccessful
        context["active"] = self.request.POST.get("observation_type")

        target = Target.objects.get(pk=self.get_target_id())
        context["target"] = target

        # allow the Facility class to add data to the context
        facility_context = facility.get_facility_context_data(target=target)
        context.update(facility_context)

        context["facility_link"] = getattr(facility, "link", "")

        try:
            context["missing_configurations"] = ", ".join(
                facility.facility_settings.get_unconfigured_settings()
            )
        except AttributeError:
            context["missing_configurations"] = ""

        return context
