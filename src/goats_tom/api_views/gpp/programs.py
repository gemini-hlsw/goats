"""Handles grabbing programs and program details from GPP."""

__all__ = ["GPPProgramViewSet"]

from asgiref.sync import async_to_sync
from gpp_client import GPPClient
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

from ._credentials import GPPCredentialsMixin


class GPPProgramViewSet(
    GPPCredentialsMixin,
    GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
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
        if (denied := self.missing_credentials(request)) is not None:
            return denied
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(token=credentials.token)
            data = async_to_sync(client.goats.get_programs)()
            programs = data.model_dump(by_alias=True)["programs"]
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

        if (denied := self.missing_credentials(request)) is not None:
            return denied
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(token=credentials.token)
            data = async_to_sync(client.program.get_by_id)(program_id=program_id)

            return Response(data.model_dump(by_alias=True)["program"])
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
