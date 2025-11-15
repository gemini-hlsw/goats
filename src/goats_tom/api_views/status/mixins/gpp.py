"""
GPP status view.
"""

__all__ = ["GPPStatusMixin"]

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from rest_framework.request import Request

from .base import BaseStatusMixin, MissingCredentialsError, Status, register_status


@register_status("gpp", "Gemini Program Platform (GPP)")
class GPPStatusMixin(BaseStatusMixin):
    service_name = "GPP"

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
        if not hasattr(request.user, "gpplogin"):
            raise MissingCredentialsError("Missing GPP login credentials")

        user = request.user
        credentials = user.gpplogin

        url = settings.GPP_URL
        if not url:
            raise MissingCredentialsError("Missing GPP URL in settings")
        return {
            "token": credentials.token,
            "url": url,
        }

    def check_service(self, credentials: dict, *args, **kwargs) -> tuple[Status, str]:
        """
        Checks the reachability of the GPP service.

        Parameters
        ----------
        credentials : dict
            A dictionary containing GPP credentials.

        Returns
        -------
        tuple[Status, str]
            A tuple containing the service status and a message.
        """
        client = GPPClient(token=credentials["token"], url=credentials["url"])
        reachable, error = async_to_sync(client.is_reachable)()
        if reachable:
            return Status.OK, "GPP service is reachable."
        else:
            return Status.DOWN, f"GPP service is unreachable: {error}"
