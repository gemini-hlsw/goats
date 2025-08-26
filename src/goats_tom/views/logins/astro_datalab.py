__all__ = ["AstroDatalabLoginView"]

from typing import Any

from goats_tom.astro_data_lab import AstroDataLabClient
from goats_tom.forms import AstroDatalabLoginForm
from goats_tom.models import AstroDatalabLogin

from .base import BaseLoginView


class AstroDatalabLoginView(BaseLoginView):
    service_name = "Astro Data Lab"
    service_description = (
        "Provide your Astro Data Lab login to enable pushing GOATS data products "
        "to your Astro Data Lab account."
    )
    model_class = AstroDatalabLogin
    form_class = AstroDatalabLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform Astro Data Lab login and logout checks.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - username : str
                The Astro Data Lab username.
            - password : str
                The Astro Data Lab password.

        Returns
        -------
        bool
            `True` if login was successful and logout executed, otherwise `False`.
        """
        with AstroDataLabClient(
            username=kwargs.get("username"), password=kwargs.get("password")
        ) as client:
            try:
                client.login()
                client.is_logged_in()
            except Exception:
                return False
        return True
