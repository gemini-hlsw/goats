"""Handles grabbing observations and observation details from GPP."""

__all__ = ["GPPObservationViewSet"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins


class GPPObservationViewSet(
    GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return a list of GPP observations associated with the authenticated user.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing a list of GPP observations.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        """
        if not hasattr(request.user, "gpplogin"):
            raise PermissionDenied(
                "GPP login credentials are not configured for this user."
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        client = GPPClient(url=settings.GPP_URL, token=credentials.token)
        observations = async_to_sync(client.observation.get_all)()

        return Response(observations)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Return details for a specific GPP observation by observation ID.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing the details of the requested observation.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        KeyError
            If 'pk' (the observation ID) is not present in kwargs.
        """
        observation_id = kwargs["pk"]

        if not hasattr(request.user, "gpplogin"):
            raise PermissionDenied(
                "GPP login credentials are not configured for this user."
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        client = GPPClient(url=settings.GPP_URL, token=credentials.token)
        observation = async_to_sync(client.observation.get_by_id)(
            observation_id=observation_id
        )

        return Response(observation)
