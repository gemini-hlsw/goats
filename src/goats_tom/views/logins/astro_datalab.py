__all__ = ["AstroDatalabLoginView"]

from goats_tom.astro_data_lab import AstroDataLabClient
from goats_tom.models import AstroDatalabLogin

from .base import BaseLoginView


class AstroDatalabLoginView(BaseLoginView):
    service_name = "Astro Data Lab"
    service_description = (
        "Provide your Astro Data Lab login to enable pushing GOATS data products "
        "to your Astro Data Lab account."
    )
    model_class = AstroDatalabLogin

    def perform_login_and_logout(self, username: str, password: str) -> bool:
        """Perform Astro Data Lab login and logout checks.

        Parameters
        ----------
        username : `str`
            The Astro Data Lab username.
        password : `str`
            The Astro Data Lab password.

        Returns
        -------
        `bool`
            `True` if login was successful and logout executed, otherwise `False`.
        """
        with AstroDataLabClient(username=username, password=password) as client:
            try:
                client.login()
                client.is_logged_in()
            except Exception:
                return False
        return True
