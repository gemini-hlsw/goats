"""Shared GPP credential handling for the GPP API views."""

__all__ = ["GPPCredentialsMixin"]

import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class GPPCredentialsMixin:
    """Answers on behalf of a view when the user has no GPP credentials."""

    def missing_credentials(self, request: Request) -> Response | None:
        """Return what to answer a user who cannot talk to GPP, if they cannot.

        The client itself is built by each view, so that the module under test
        is the one holding it.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response | None
            The answer explaining what is missing, or ``None`` when the user
            does have credentials stored.
        """
        if hasattr(request.user, "gpplogin"):
            return None

        logger.error(
            "GPP login credentials are not configured for user: %s", request.user
        )
        return Response(
            {"detail": "GPP login credentials are not configured for this user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
