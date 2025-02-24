__all__ = ["GOALoginView"]

from goats_tom.astroquery import Observations as GOA
from goats_tom.models import GOALogin

from .base import BaseLoginView


class GOALoginView(BaseLoginView):
    service_name = "GOA"
    service_description = (
        "Provide your GOA login to allow GOATS to download proprietary data "
        "associated with your GOA account."
    )
    model_class = GOALogin

    def perform_login_and_logout(self, username: str, password: str) -> bool:
        """Perform GOA login and logout checks.

        Parameters
        ----------
        username : `str`
            The GOA username.
        password : `str`
            The GOA password.

        Returns
        -------
        `bool`
            `True` if login was successful and logout executed, otherwise `False`.
        """
        GOA.login(username, password)
        if not GOA.authenticated():
            return False
        GOA.logout()
        return True
