"""Handles grabbing approved configuration requests from GPP."""

__all__ = ["GPPConfigurationRequestViewSet"]

import logging

from asgiref.sync import async_to_sync
from gpp_client import GPPClient
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

from ._credentials import GPPCredentialsMixin

logger = logging.getLogger(__name__)


class GPPConfigurationRequestViewSet(
    GPPCredentialsMixin, GenericViewSet, mixins.ListModelMixin
):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return the approved configuration requests for a GPP program.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context. Requires a
            ``program_id`` query parameter.

        Returns
        -------
        Response
            A DRF Response object containing the approved configuration requests.
        """
        if (denied := self.missing_credentials(request)) is not None:
            return denied

        program_id = request.query_params.get("program_id")
        if program_id is None:
            return Response(
                {"detail": "A 'program_id' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger.debug(
                "Retrieving GPP configuration requests for program ID: %s", program_id
            )
            client = GPPClient(token=request.user.gpplogin.token)
            payload = async_to_sync(
                client.goats.get_configuration_requests_by_program_id
            )(program_id=program_id)
            data = payload.model_dump(by_alias=True)["configurationRequests"]
            return Response(
                {
                    "matches": data.get("matches", []),
                    "hasMore": data.get("hasMore", False),
                }
            )
        except Exception as e:
            logger.exception("Error retrieving GPP configuration requests")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
