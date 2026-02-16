__all__ = ["RefreshAntaresPhotometryView"]
import logging

from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from tom_alerts.alerts import get_service_class as tom_alerts_get_service_class
from tom_targets.models import Target

logger = logging.getLogger(__name__)


@method_decorator(require_POST, name="dispatch")
class RefreshAntaresPhotometryView(View):
    def post(self, request, target_id: int):
        target = get_object_or_404(Target, pk=target_id)
        locusid = target.name

        logger.debug(
            "ANTARES refresh: start target_id=%s target_name=%s locusid=%s",
            target_id,
            target.name,
            locusid,
        )

        broker = tom_alerts_get_service_class("ANTARES")()

        alerts = list(broker.fetch_alerts({"locusid": locusid}))
        if not alerts:
            logger.debug(
                "ANTARES refresh: no alerts found locusid=%s target_id=%s",
                locusid,
                target_id,
            )
            return redirect(request.META.get("HTTP_REFERER", "/"))

        alert = alerts[0]
        logger.debug("ANTARES refresh: fetched alert locusid=%s", locusid)

        lightcurve_data = broker.process_lightcurve_data(alert=alert)
        has_data = lightcurve_data is not None and not lightcurve_data.empty
        logger.debug(
            "ANTARES refresh: processed lightcurve locusid=%s has_data=%s",
            locusid,
            has_data,
        )
        if not has_data:
            return redirect(request.META.get("HTTP_REFERER", "/"))

        try:
            dp = broker.create_lightcurve_dp(target, lightcurve_data)
            logger.debug(
                "ANTARES refresh: lightcurve DataProduct dp_id=%s target_id=%s",
                getattr(dp, "id", None),
                target_id,
            )
            broker.create_reduced_datums(dp)
            logger.debug(
                "ANTARES refresh: created reduced datums dp_id=%s target_id=%s",
                getattr(dp, "id", None),
                target_id,
            )
        except Exception:
            logger.exception(
                "ANTARES refresh: failed target_id=%s locusid=%s", target_id, locusid
            )

        return redirect(request.META.get("HTTP_REFERER", "/"))
