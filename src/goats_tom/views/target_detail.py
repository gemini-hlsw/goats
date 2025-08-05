__all__ = ["TargetDetailView"]

import logging
from io import StringIO
from urllib.parse import urlencode

from django.contrib import messages
from django.core.management import call_command
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from tom_common.hints import add_hint
from tom_observations.models import ObservationTemplate
from tom_observations.observation_template import ApplyObservationTemplateForm
from tom_targets.views import TargetDetailView as BaseTargetDetailView

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TargetDetailView(BaseTargetDetailView):
    def get(self, request, *args, **kwargs):
        """
        Override for the tomtoolkit method to pass the user for user api-key.
        """
        update_status = request.GET.get("update_status", False)
        if update_status:
            if not request.user.is_authenticated:
                return redirect(reverse("login"))
            target_id = kwargs.get("pk", None)
            out = StringIO()
            call_command(
                "updatestatus",
                target_id=target_id,
                # Provide the username so the facility is updated.
                username=request.user.username,
                stdout=out,
            )
            messages.info(request, out.getvalue())
            add_hint(
                request,
                mark_safe(
                    "Did you know updating observation statuses can be automated? Learn"
                    " how in <a href=https://tom-toolkit.readthedocs.io/en/stable/customization/automation.html>"
                    " the docs.</a>"
                ),
            )
            return redirect(
                reverse("tom_targets:detail", args=(target_id,)) + "?tab=observations"
            )

        obs_template_form = ApplyObservationTemplateForm(request.GET)
        if obs_template_form.is_valid():
            obs_template = ObservationTemplate.objects.get(
                pk=obs_template_form.cleaned_data["observation_template"].id
            )
            obs_template_params = obs_template.parameters
            obs_template_params["cadence_strategy"] = request.GET.get(
                "cadence_strategy", ""
            )
            obs_template_params["cadence_frequency"] = request.GET.get(
                "cadence_frequency", ""
            )
            params = urlencode(obs_template_params)
            return redirect(
                reverse("tom_observations:create", args=(obs_template.facility,))
                + f"?target_id={self.get_object().id}&"
                + params
            )

        return super().get(request, *args, **kwargs)
