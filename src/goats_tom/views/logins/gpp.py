__all__ = ["GPPLoginView"]

from typing import Any

from goats_tom.forms import GPPLoginForm
from goats_tom.models import GPPLogin
from goats_tom.service_checks import CheckResult, check_gpp

from .base import BaseLoginView


class GPPLoginView(BaseLoginView):
    service_name = "GPP"
    service_description = (
        "Provide your GPP token to enable communication with GPP, allowing a user to "
        "trigger ToOs and modify observations."
    )
    model_class = GPPLogin
    form_class = GPPLoginForm

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Check a GPP token.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - token : str
                The authentication token to use for the GPP client.

        Returns
        -------
        CheckResult
            Whether the credentials were accepted and, if not, whether the
            service could be reached.
        """
        return check_gpp(kwargs.get("token"))
