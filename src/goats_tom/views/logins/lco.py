__all__ = ["LCOLoginView"]

from typing import Any

import requests
from django.conf import settings

from goats_tom.forms import LCOLoginForm
from goats_tom.models import LCOLogin

from .base import BaseLoginView


class LCOLoginView(BaseLoginView):
    service_name = "LCO"
    service_description = (
        "Provide your API key from your "
        '<a href="https://observe.lco.global" target="_blank">LCO portal account</a>. '
        "This is required to be able to trigger LCO or SOAR."
    )
    model_class = LCOLogin
    form_class = LCOLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform check using a token.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - token : str
                The authentication token to use for the GPP client.

        Returns
        -------
        bool
            `True` if the endpoint is reachable and the token is valid, `False`
            otherwise.
        """
        token = kwargs.get("token")
        url = settings.FACILITIES.get("LCO").get("portal_url")
        try:
            response = requests.get(
                f"{url}/api/proposals/", headers={"Authorization": f"Token {token}"}
            )
            response.raise_for_status()
        except Exception:
            return False
        return True
