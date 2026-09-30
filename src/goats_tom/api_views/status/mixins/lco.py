"""
LCO status view.
"""

__all__ = ["LCOStatusMixin"]

from django.conf import settings
from rest_framework.request import Request

from goats_tom.credentials import require_credentials
from goats_tom.models import LCOLogin
from goats_tom.service_checks import CheckResult, check_lco

from .base import BaseStatusMixin, register_status


@register_status(
    "lco",
    "Las Cumbres Observatory (LCO)",
    manage_url_name="user-lco-login",
)
class LCOStatusMixin(BaseStatusMixin):
    service_name = "LCO"

    def get_public_url(self) -> str:
        """
        Returns the LCO portal URL checked when no credentials are stored.

        Returns
        -------
        str
            The URL to request.
        """
        return settings.FACILITIES["LCO"]["portal_url"]

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves the LCO API key from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            A dictionary with the LCO API key.

        Raises
        ------
        MissingCredentialsError
            If the user has no LCO API key stored.
        """
        credentials = require_credentials(LCOLogin, user=request.user)
        return {"token": credentials.token}

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks that LCO accepts the stored API key.

        Parameters
        ----------
        credentials : dict
            A dictionary containing the LCO API key.

        Returns
        -------
        CheckResult
            The outcome of the check.
        """
        return check_lco(**credentials)
