"""
GPP status view.
"""

__all__ = ["GPPStatusMixin"]

from django.conf import settings
from gpp_client.settings import GPPSettings
from rest_framework.request import Request

from goats_tom.credentials import require_credentials
from goats_tom.models import GPPLogin
from goats_tom.service_checks import CheckResult, check_gpp, check_gpp_reachable

from .base import BaseStatusMixin, MissingCredentialsError, register_status


@register_status(
    "gpp",
    "Gemini Program Platform (GPP)",
    url="https://explore.gemini.edu",
    url_label="Explore",
    manage_url_name="user-gpp-login",
)
class GPPStatusMixin(BaseStatusMixin):
    service_name = "GPP"

    def get_public_url(self) -> str:
        """
        Returns the GPP URL checked when no token is stored.

        Returns
        -------
        str
            The base URL of the GPP environment the client targets.
        """
        return GPPSettings().environment.base_url

    def check_public(self) -> CheckResult:
        """
        Checks that GPP answers the client's ping query, without a token.

        Returns
        -------
        CheckResult
            The outcome. The server's root answers 404, so it cannot tell.
        """
        return check_gpp_reachable()

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves GPP credentials from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            A dictionary of GPP credentials.

        Raises
        ------
        MissingCredentialsError
            If GPP credentials are missing in the request.
        """
        # Retrieve GPP credentials from the request.
        credentials = require_credentials(GPPLogin, user=request.user)

        env = settings.GPP_ENV
        if not env:
            raise MissingCredentialsError("Missing GPP environment in settings")
        return {
            "token": credentials.token,
            "env": env,
        }

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks the reachability of the GPP service.

        Parameters
        ----------
        credentials : dict
            A dictionary containing GPP credentials.

        Returns
        -------
        CheckResult
            The outcome of the check.
        """
        return check_gpp(credentials["token"])
