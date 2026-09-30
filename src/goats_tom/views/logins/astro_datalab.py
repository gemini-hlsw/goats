__all__ = ["AstroDatalabLoginView"]

from typing import Any

from goats_tom.forms import AstroDatalabLoginForm
from goats_tom.models import AstroDatalabLogin
from goats_tom.service_checks import CheckResult, check_astro_datalab

from .base import BaseLoginView


class AstroDatalabLoginView(BaseLoginView):
    service_name = "Astro Data Lab"
    service_description = (
        "Provide your Astro Data Lab login to enable pushing GOATS data products "
        "to your Astro Data Lab account."
    )
    model_class = AstroDatalabLogin
    form_class = AstroDatalabLoginForm

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Check Astro Data Lab credentials by signing in.

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
        CheckResult
            Whether the credentials were accepted and, if not, whether the
            service could be reached.
        """
        return check_astro_datalab(kwargs.get("username"), kwargs.get("password"))
