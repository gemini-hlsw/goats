"""
Provides custom endpoints to interact with GPP GraphQL service.
"""

__all__ = ["GPPViewSet"]

from asgiref.sync import async_to_sync
from gpp_client import GPPClient
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ._credentials import GPPCredentialsMixin


class GPPViewSet(GPPCredentialsMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def ping(self, request: Request) -> Response:
        """
        Check if the GPP endpoint is reachable for the authenticated user.

        Returns
        -------
        Response
            A response indicating whether the GPP connection was successful.
            If the user's GPP credentials are missing, returns HTTP 403.
            If the endpoint is unreachable, returns HTTP 502.
            Otherwise, returns HTTP 200 with success detail.
        """
        if (denied := self.missing_credentials(request)) is not None:
            return denied

        credentials = request.user.gpplogin
        client = GPPClient(token=credentials.token)
        reachable, error = async_to_sync(client.ping)()

        if reachable:
            return Response({"detail": "Successfully connected to GPP."})
        else:
            return Response(
                {"detail": f"Failed to connect to GPP. {error}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
