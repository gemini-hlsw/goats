__all__ = ["GOALoginView"]

from typing import Any

from goats_tom.forms import GOALoginForm
from goats_tom.models import GOALogin
from goats_tom.service_checks import CheckResult, check_goa

from .base import BaseLoginView


class GOALoginView(BaseLoginView):
    service_name = "GOA"
    service_description = (
        "Provide your GOA login to allow GOATS to download proprietary data "
        "associated with your GOA account."
    )
    model_class = GOALogin
    form_class = GOALoginForm

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Check GOA credentials by signing in and out.

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
        CheckResult
            Whether the credentials were accepted and, if not, whether the
            service could be reached.
        """
        return check_goa(kwargs.get("username"), kwargs.get("password"))
