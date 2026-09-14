"""Handles grabbing the valid instrument configuration options from GPP."""

__all__ = ["GPPConfigOptionsViewSet"]

import logging

from asgiref.sync import async_to_sync
from gpp_client import GPPClient
from gpp_client.generated.enums import Instrument
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

from ._credentials import GPPCredentialsMixin

logger = logging.getLogger(__name__)


class GPPConfigOptionsViewSet(
    GPPCredentialsMixin, GenericViewSet, mixins.ListModelMixin
):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return the configuration options an instrument supports.

        These are the combinations the observatory offers, so the observation
        form can offer only the FPUs that go with an approved disperser and
        propose the wavelength recommended for them.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context. Requires an
            ``instrument`` query parameter.

        Returns
        -------
        Response
            A DRF Response object with the spectroscopy and imaging options.
        """
        if (denied := self.missing_credentials(request)) is not None:
            return denied

        instrument = request.query_params.get("instrument")
        if instrument is None:
            return Response(
                {"detail": "An 'instrument' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instrument not in {i.value for i in Instrument}:
            return Response(
                {"detail": f"'{instrument}' is not a known instrument."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger.debug("Retrieving GPP config options for instrument: %s", instrument)
            client = GPPClient(token=request.user.gpplogin.token)
            payload = async_to_sync(client.goats.get_config_options)(
                instrument=instrument
            )
            data = payload.model_dump(by_alias=True)
            return Response(
                {
                    "spectroscopy": data.get("spectroscopyConfigOptions", []),
                    "imaging": data.get("imagingConfigOptions", []),
                }
            )
        except Exception as e:
            logger.exception("Error retrieving GPP config options")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
