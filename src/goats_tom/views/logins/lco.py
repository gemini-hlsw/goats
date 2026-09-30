__all__ = ["LCOLoginView"]

from typing import Any

from goats_tom.forms import LCOLoginForm
from goats_tom.models import LCOLogin
from goats_tom.service_checks import CheckResult, check_lco

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

    def verify_credentials(self, **kwargs: Any) -> CheckResult:
        """Check an LCO API key.

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
        return check_lco(kwargs.get("token"))
