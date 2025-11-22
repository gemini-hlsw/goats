"""
Status API ViewSet.
"""

__all__ = ["StatusViewSet"]

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .mixins import status_mixins


class StatusViewSet(ViewSet):
    """
    Provides endpoints to check the status of various services.
    """

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        Returns a list of available service status endpoints.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        Response
            A response containing available service status endpoints.
        """
        services = [
            {
                "name": name,
                "display_name": meta["display_name"],
                "endpoint": meta["endpoint"],
            }
            for name, meta in status_mixins.items()
        ]

        return Response(
            {
                "message": "Available services and details",
                "services": services,
                "status_codes": {
                    "ok": "Service is operational",
                    "warning": "Service is experiencing issues",
                    "down": "Service is down",
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, url_path="(?P<service>[^/]+)", methods=["get"])
    def status_router(self, request: Request, service: str) -> Response:
        """
        Routes the status check request to the appropriate service mixin.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.
        service : str
            The service name to check status for.

        Returns
        -------
        Response
            A response containing the service status.
        """
        entry = status_mixins.get(service)
        if not entry:
            return Response(
                {"detail": f"Unknown status service: {service}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mixin = entry["instance"]
        return mixin.get(request)
