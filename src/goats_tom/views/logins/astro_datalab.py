__all__ = ["AstroDatalabLoginView"]

from goats_tom.models import AstroDatalabLogin

from .base import BaseLoginView


class AstroDatalabLoginView(BaseLoginView):
    service_name = "Astro Datalab"
    service_description = (
        "Provide your Astro Datalab login to enable pushing GOATS data products "
        "to your Astro Datalab account."
    )
    model_class = AstroDatalabLogin

    def perform_login_and_logout(self, username: str, password: str) -> bool:
        """Perform Astro Datalab login and logout checks.

        Parameters
        ----------
        username : `str`
            The Astro Datalab username.
        password : `str`
            The Astro Datalab password.

        Returns
        -------
        `bool`
            `True` if login was successful and logout executed, otherwise `False`.
        """
        from dl import authClient as ac

        token = ac.login(username, password)
        if not ac.isValidToken(token):
            return False
        ac.logout(token)
        return True
