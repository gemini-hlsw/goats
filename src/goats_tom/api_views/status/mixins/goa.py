"""
GOA status view.
"""

__all__ = ["GOAStatusMixin"]

from rest_framework.request import Request

from goats_tom.astroquery import conf as goa_conf
from goats_tom.credentials import require_credentials
from goats_tom.models import GOALogin
from goats_tom.service_checks import CheckResult, check_goa

from .base import BaseStatusMixin, register_status


@register_status(
    "goa",
    "Gemini Observatory Archive (GOA)",
    manage_url_name="user-goa-login",
)
class GOAStatusMixin(BaseStatusMixin):
    service_name = "GOA"

    def get_public_url(self) -> str:
        """
        Returns the GOA URL checked when no credentials are stored.

        Returns
        -------
        str
            The URL to request.
        """
        return goa_conf.GOA_SERVER

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves GOA credentials from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            A dictionary of GOA credentials.

        Raises
        ------
        MissingCredentialsError
            If the user has no GOA credentials stored.
        """
        credentials = require_credentials(GOALogin, user=request.user)
        return {"username": credentials.username, "password": credentials.password}

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks that GOA accepts the stored credentials.

        Parameters
        ----------
        credentials : dict
            A dictionary containing GOA credentials.

        Returns
        -------
        CheckResult
            The outcome of the check.
        """
        return check_goa(**credentials)
