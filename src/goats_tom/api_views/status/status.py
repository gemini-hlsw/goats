"""
Status API ViewSet.
"""

__all__ = ["StatusViewSet"]

from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .mixins import status_mixins


class StatusViewSet(ViewSet):
    """
    Provides endpoints to check the status of various services.
    """

    permission_classes = [permissions.IsAuthenticated]

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
                "group": meta["group"],
                "url": meta["url"] or meta["instance"].get_public_url(),
                "url_label": meta["url_label"] or meta["display_name"],
                "manage_url": self._manage_url(request, meta["manage_url_name"]),
            }
            for name, meta in status_mixins.items()
        ]

        return Response(
            {
                "message": "Available services and details",
                "services": services,
                "status_codes": {
                    "ok": "Service is available",
                    "down": "Service is not available",
                    "unknown": "Service could not be checked",
                },
                "credential_codes": {
                    "verified": "Stored credentials were accepted",
                    "rejected": "Stored credentials were rejected",
                    "missing": "No credentials are stored",
                    "unverifiable": "Stored credentials cannot be verified",
                    "unchecked": "Credentials were not checked",
                },
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _manage_url(request: Request, url_name: str | None) -> str | None:
        """
        Returns the page managing the requester's credentials for a service.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.
        url_name : str | None
            The URL name of the credentials page, if the service has one.

        Returns
        -------
        str | None
            The page's path, or `None` if there is none or no signed-in user.
        """
        if url_name is None or not request.user.is_authenticated:
            return None
        return reverse(url_name, kwargs={"pk": request.user.pk})

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
