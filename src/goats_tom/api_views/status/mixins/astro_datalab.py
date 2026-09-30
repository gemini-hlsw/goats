"""
Astro Data Lab status view.
"""

__all__ = ["AstroDatalabStatusMixin"]

from rest_framework.request import Request

from goats_tom.astro_data_lab.config import AstroDataLabConfig
from goats_tom.credentials import require_credentials
from goats_tom.models import AstroDatalabLogin
from goats_tom.service_checks import CheckResult, check_astro_datalab

from .base import BaseStatusMixin, register_status


@register_status(
    "astro-data-lab",
    "Astro Data Lab",
    manage_url_name="user-astro-data-lab-login",
)
class AstroDatalabStatusMixin(BaseStatusMixin):
    service_name = "Astro Data Lab"

    def get_public_url(self) -> str:
        """
        Returns the Astro Data Lab URL checked when no credentials are stored.

        Returns
        -------
        str
            The URL to request.
        """
        return AstroDataLabConfig().base_url

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves Astro Data Lab credentials from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            A dictionary of Astro Data Lab credentials.

        Raises
        ------
        MissingCredentialsError
            If the user has no Astro Data Lab credentials stored.
        """
        credentials = require_credentials(AstroDatalabLogin, user=request.user)
        return {"username": credentials.username, "password": credentials.password}

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks that Astro Data Lab accepts the stored credentials.

        Parameters
        ----------
        credentials : dict
            A dictionary containing Astro Data Lab credentials.

        Returns
        -------
        CheckResult
            The outcome of the check.
        """
        return check_astro_datalab(**credentials)
