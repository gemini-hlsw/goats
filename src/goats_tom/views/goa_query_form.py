__all__ = ["GOAQueryFormView"]
from django.contrib import messages
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import View
from tom_observations.models import ObservationRecord

from goats_tom.astroquery import Observations as GOA
from goats_tom.forms import GOAQueryForm
from goats_tom.models import GOALogin
from goats_tom.tasks import download_goa_files


class GOAQueryFormView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle POST requests.

        Parameters
        ----------
        request : `HttpRequest`
            The request object.

        Returns
        -------
        `HttpResponse`
            The response object.

        Notes
        -----
        Requires `change_observationrecord`. Downloading from GOA writes new
        data products onto somebody else's observation and consumes their
        proprietary-data entitlement, so it is not something a read-only
        recipient of a share should be able to start.

        Checked here rather than only in the template that renders the form.
        The detail page hides the form from a read-only viewer, but hiding a
        form does not stop a POST, and this endpoint is reachable by anyone
        who knows the URL.
        """
        # Check if your GOAQueryForm was submitted.
        form = GOAQueryForm(request.POST)
        observation_record = get_object_or_404(ObservationRecord, pk=kwargs["pk"])
        observation_detail_url = reverse(
            "tom_observations:detail", kwargs={"pk": kwargs["pk"]}
        )

        if not (
            request.user.is_superuser
            or request.user.has_perm(
                "tom_observations.change_observationrecord", observation_record
            )
        ):
            messages.error(
                request,
                "You do not have permission to download data for this observation.",
            )
            return redirect(observation_detail_url)

        if form.is_valid():
            # Get GOA credentials.
            prop_data_msg = "Proprietary data will not be downloaded."
            try:
                goa_credentials = GOALogin.objects.get(user=request.user)
                # Login to GOA.
                GOA.login(goa_credentials.username, goa_credentials.password)
                if not GOA.authenticated():
                    raise PermissionError
                GOA.logout()

            except GOALogin.DoesNotExist:
                messages.warning(
                    request,
                    f"GOA login credentials not found. {prop_data_msg}",
                )
            except PermissionError:
                messages.warning(
                    request,
                    f"GOA login failed. Re-enter login credentials. {prop_data_msg}",
                )

            query_params = form.cleaned_data["query_params"]

            # Download in background.
            download_goa_files.send(
                observation_record.id,
                query_params,
                request.user.id,
            )
            messages.info(request, "Downloading data in background. Check back soon!")

        else:
            # Pass the form with errors to the template
            for field, errors in form.errors.items():
                for error in errors:
                    msg = f"Error in {field}: {error}"
                    messages.error(request, msg)

        return redirect(observation_detail_url)
