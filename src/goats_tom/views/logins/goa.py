__all__ = ["GOALoginView"]

from typing import Any

from goats_tom.astroquery import Observations as GOA
from goats_tom.forms import GOALoginForm
from goats_tom.models import GOALogin

from .base import BaseLoginView


class GOALoginView(BaseLoginView):
    service_name = "GOA"
    service_description = (
        "Provide your GOA login to allow GOATS to download proprietary data "
        "associated with your GOA account."
    )
    model_class = GOALogin
    form_class = GOALoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform GOA login and logout checks.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - username : str
                The GOA username.
            password : str
                The GOA password.

        Returns
        -------
        bool
            `True` if login was successful and logout executed, otherwise `False`.
        """
        GOA.login(kwargs.get("username"), kwargs.get("password"))
        if not GOA.authenticated():
            return False
        GOA.logout()
        return True
