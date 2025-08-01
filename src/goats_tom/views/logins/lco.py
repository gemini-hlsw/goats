__all__ = ["LCOLoginView"]

from typing import Any

from django.conf import settings

from goats_tom.forms import TokenLoginForm
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
    form_class = TokenLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform login check using a token.

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
        _ = kwargs.get("token")
        _ = settings.FACILITIES["LCO"]["portal_url"]
        # FIXME: For now, just return True until we figure out a small test to login.
        return True
