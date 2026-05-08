__all__ = ["RefreshAntaresPhotometryView"]
import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from tom_alerts.alerts import get_service_class as tom_alerts_get_service_class
from tom_targets.models import Target

logger = logging.getLogger(__name__)


def _back(request):
    return request.META.get("HTTP_REFERER") or "/targets/"


@method_decorator(require_POST, name="dispatch")
class RefreshAntaresPhotometryView(View):
    def post(self, request, target_id: int):
        target = get_object_or_404(Target, pk=target_id)

        antares_name = next(
            (n for n in target.names if n.upper().startswith("ANT")), None
        )

        if not antares_name:
            messages.error(request, "Target has no ANTARES identifier.")
            return redirect(_back(request))

        locusid = antares_name

        logger.debug(
            "ANTARES refresh: start target_id=%s target_name=%s locusid=%s",
            target_id,
            target.name,
            locusid,
        )

        broker = tom_alerts_get_service_class("ANTARES")()

        alert = next(broker.fetch_alerts({"locusid": locusid}), None)

        if not alert:
            logger.debug(
                "ANTARES refresh: no alerts found locusid=%s target_id=%s",
                locusid,
                target_id,
            )
            return redirect(_back(request))

        logger.debug("ANTARES refresh: fetched alert locusid=%s", locusid)

        lightcurve_data = broker.process_lightcurve_data(alert=alert)
        has_data = lightcurve_data is not None and not lightcurve_data.empty

        if not has_data:
            return redirect(_back(request))

        try:
            dp = broker.create_lightcurve_dp(target, lightcurve_data)

            logger.debug(
                "ANTARES refresh: lightcurve DataProduct dp_id=%s target_id=%s",
                getattr(dp, "id", None),
                target_id,
            )

            broker.create_reduced_datums(dp)

            messages.success(request, "Photometry updated successfully.")

        except Exception:
            logger.exception(
                "ANTARES refresh: failed target_id=%s locusid=%s",
                target_id,
                locusid,
            )
            messages.error(request, "Failed to update photometry.")

        return redirect(_back(request))
