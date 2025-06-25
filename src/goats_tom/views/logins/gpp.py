__all__ = ["GPPLoginView"]

from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient

from goats_tom.forms import TokenLoginForm
from goats_tom.models import GPPLogin

from .base import BaseLoginView


class GPPLoginView(BaseLoginView):
    service_name = "GPP"
    service_description = (
        "Provide your GPP token to enable communication with GPP, allowing a user to "
        "trigger ToOs and modify observations."
    )
    model_class = GPPLogin
    form_class = TokenLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform GPP login check using a token.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - token : str
                The authentication token to use for the GPP client.

        Returns
        -------
        bool
            `True` if the GPP endpoint is reachable and the token is valid, `False`
            otherwise.
        """
        token = kwargs.get("token")
        client = GPPClient(url=settings.GPP_URL, token=token)

        # FIXME: Hack until we get fix in GPP client.
        query = """
            {
                __schema {
                    queryType {
                        name
                    }
                }
            }
        """
        try:
            response = async_to_sync(client._client.execute)(query)
            response.raise_for_status()
        except Exception:
            return False
        return True
