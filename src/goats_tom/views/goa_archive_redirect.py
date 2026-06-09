__all__ = ["GOAArchiveRedirectView"]

import logging
from urllib.parse import urlparse

import requests
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from tom_observations.models import ObservationRecord

from goats_tom.astroquery import Observations as GOA
from goats_tom.astroquery.conf import conf as goa_conf
from goats_tom.models import GOALogin

logger = logging.getLogger(__name__)


class GOAArchiveRedirectView(View):
    def get(self, request: HttpRequest, pk: int, *args, **kwargs) -> HttpResponse:
        observation_record = get_object_or_404(ObservationRecord, pk=pk)
        archive_url = observation_record.url
        observation_detail_url = reverse("tom_observations:detail", kwargs={"pk": pk})
        goa_login_url = reverse("user-goa-login", kwargs={"pk": request.user.pk})

        if not archive_url:
            messages.warning(request, "No archive URL available for this observation.")
            return redirect(observation_detail_url)

        try:
            response = requests.head(archive_url, timeout=5, allow_redirects=True)
            logger.debug("GOA archive response: status=%s", response.status_code)
        except requests.RequestException:
            logger.exception("Failed to reach GOA archive URL: %s", archive_url)
            messages.warning(
                request, "The Gemini Observatory Archive is not responding."
            )
            return redirect(observation_detail_url)

        if response.status_code in (200, 302):
            return redirect(archive_url)

        if response.status_code == 403:
            try:
                credentials = GOALogin.objects.get(user=request.user)
            except GOALogin.DoesNotExist:
                return redirect(goa_login_url)

            # Validate credentials are still valid before exposing them.
            GOA.login(credentials.username, credentials.password)
            if not GOA.authenticated():
                GOA.logout()
                messages.warning(
                    request, "Your GOA credentials are invalid. Please update them."
                )
                return redirect(goa_login_url)
            GOA.logout()

            http_response = render(
                request,
                "tom_observations/goa_archive_login.html",
                {
                    "goa_login_url": f"{goa_conf.GOA_SERVER}/login/",
                    "username": credentials.username,
                    "password": credentials.password,
                    "archive_path": urlparse(archive_url).path,
                },
            )
            http_response["Cache-Control"] = "no-store"
            return http_response

        messages.warning(request, "The Gemini Observatory Archive is not available.")
        return redirect(observation_detail_url)
