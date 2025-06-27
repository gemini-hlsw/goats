"""Handles grabbing programs and program details from GPP."""

__all__ = ["GPPProgramViewSet"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
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
            raise PermissionDenied(
                "GPP login credentials are not configured for this user."
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        client = GPPClient(url=settings.GPP_URL, token=credentials.token)
        programs = async_to_sync(client.program.get_all)()

        return Response(programs)

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
            raise PermissionDenied(
                "GPP login credentials are not configured for this user."
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        client = GPPClient(url=settings.GPP_URL, token=credentials.token)
        program = async_to_sync(client.program.get_by_id)(program_id=program_id)

        return Response(program)
