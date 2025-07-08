"""Handles grabbing observations and observation details from GPP."""

__all__ = ["GPPObservationViewSet"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.input_types import (
    WhereObservation,
    WhereOrderProgramId,
    WhereProgram,
)
from rest_framework import permissions, status
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
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        credentials = request.user.gpplogin

        program_id = request.query_params.get("program_id")

        try:
            # Setup client to communicate with GPP.
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            if program_id is not None:
                where = self._build_where(program_id)
                observations = async_to_sync(client.observation.get_all)(where=where)
            else:
                observations = async_to_sync(client.observation.get_all)()
            return Response(observations)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            observation = async_to_sync(client.observation.get_by_id)(
                observation_id=observation_id
            )
            return Response(observation)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _build_where(self, program_id: str) -> WhereObservation:
        """Build the filter to filter by program ID."""
        where = WhereObservation(
            program=WhereProgram(id=WhereOrderProgramId(eq=program_id))
        )

        return where
