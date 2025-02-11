__all__ = ["GOAQueryFormView"]
from django.contrib import messages
from django.core import serializers
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import View
from tom_observations.models import ObservationRecord

from goats_tom.astroquery import Observations as GOA
from goats_tom.forms import GOAQueryForm
from goats_tom.models import GOALogin
from goats_tom.tasks import download_goa_files


class GOAQueryFormView(View):
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

        """
        # Check if your GOAQueryForm was submitted.
        form = GOAQueryForm(request.POST)
        observation_record = ObservationRecord.objects.get(pk=kwargs["pk"])
        observation_detail_url = reverse(
            "tom_observations:detail", kwargs={"pk": kwargs["pk"]}
        )

        # Check if the observation status is valid, if not stop here and issue message.
        if observation_record.status.lower() != "observed":
            messages.error(
                request,
                (
                    "GOA data is unavailable until the observation is complete. Update "
                    "the observation status on the overview page once it's finished."
                ),
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

            serialized_observation_record = serializers.serialize(
                "json",
                [observation_record],
            )
            # Download in background.
            download_goa_files.send(
                serialized_observation_record,
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
