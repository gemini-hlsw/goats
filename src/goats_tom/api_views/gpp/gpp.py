"""
Provides custom endpoints to interact with GPP GraphQL service.
"""

__all__ = ["GPPViewSet"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response


class GPPViewSet(viewsets.GenericViewSet):
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
        if not hasattr(request.user, "gpplogin"):
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        credentials = request.user.gpplogin
        client = GPPClient(token=credentials.token, url=settings.GPP_URL)
        reachable, error = async_to_sync(client.is_reachable)()

        if reachable:
            return Response({"detail": "Successfully connected to GPP."})
        else:
            return Response(
                {"detail": f"Failed to connect to GPP. {error}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
