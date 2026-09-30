"""
TNS status view.
"""

__all__ = ["TNSStatusMixin"]

import json

from django.conf import settings
from rest_framework.request import Request

from goats_tom.credentials import require_credentials
from goats_tom.models import TNSLogin
from goats_tom.service_checks import CheckResult

from .base import BaseStatusMixin, register_status


@register_status(
    "tns",
    "Transient Name Server (TNS)",
    manage_url_name="user-tns-login",
)
class TNSStatusMixin(BaseStatusMixin):
    service_name = "TNS"

    def get_public_url(self) -> str:
        """
        Returns the TNS URL checked for reachability.

        Returns
        -------
        str
            The URL to request.
        """
        return settings.BROKERS.get("TNS", {}).get(
            "tns_base_url", "https://www.wis-tns.org/"
        )

    def get_public_headers(self) -> dict[str, str]:
        """
        Returns the bot User-Agent TNS requires of API clients.

        Returns
        -------
        dict[str, str]
            The headers. TNS answers 403 to any other client.
        """
        marker = json.dumps({"tns_id": 0, "type": "bot", "name": "GOATS"})
        return {"User-Agent": f"tns_marker{marker}"}

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves TNS credentials from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            An empty dictionary; only whether credentials exist matters.

        Raises
        ------
        MissingCredentialsError
            If the user has no TNS credentials stored.
        """
        require_credentials(TNSLogin, user=request.user)
        return {}

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks that TNS is up; the stored credentials cannot be verified.

        Parameters
        ----------
        credentials : dict
            Unused.

        Returns
        -------
        CheckResult
            The outcome, marked unverified.
        """
        # Same as the TNS credentials form: the credentials cannot be checked.
        result = self.check_public()
        if not result.ok:
            return result
        return CheckResult(
            True, "GOATS does not verify TNS credentials automatically.", verified=False
        )
