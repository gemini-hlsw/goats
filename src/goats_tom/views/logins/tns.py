__all__ = ["TNSLoginView"]

from typing import Any

from goats_tom.forms import TNSLoginForm
from goats_tom.models import TNSLogin

from .base import BaseLoginView


class TNSLoginView(BaseLoginView):
    service_name = "TNS"
    service_description = (
        "Provide the following details to be able to communicate with TNS."
    )
    model_class = TNSLogin
    form_class = TNSLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        # TODO: Figure out if there is a test or not.
        return True
