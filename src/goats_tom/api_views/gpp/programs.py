"""Handles grabbing programs and program details from GPP."""

__all__ = ["GPPProgramViewSet"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.enums import ProposalStatus
from gpp_client.api.input_types import (
    WhereEqProposalStatus,
    WhereProgram,
)
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins


class GPPProgramViewSet(
    GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return a list of GPP programs associated with the authenticated user.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing a list of GPP programs.

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

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            # Filter by accepted proposals.
            where = WhereProgram(
                proposal_status=WhereEqProposalStatus(eq=ProposalStatus.ACCEPTED)
            )
            programs = async_to_sync(client.program.get_all)(where=where)

            return Response(programs)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Return details for a specific GPP program by program ID.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing the details of the requested program.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        KeyError
            If 'pk' (the program ID) is not present in kwargs.
        """
        program_id = kwargs["pk"]

        if not hasattr(request.user, "gpplogin"):
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            program = async_to_sync(client.program.get_by_id)(program_id=program_id)

            return Response(program)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
