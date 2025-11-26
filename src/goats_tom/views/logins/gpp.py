__all__ = ["GPPLoginView"]

import logging
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient

from goats_tom.forms import GPPLoginForm
from goats_tom.models import GPPLogin

from .base import BaseLoginView

logger = logging.getLogger(__name__)


class GPPLoginView(BaseLoginView):
    service_name = "GPP"
    service_description = (
        "Provide your GPP token to enable communication with GPP, allowing a user to "
        "trigger ToOs and modify observations."
    )
    model_class = GPPLogin
    form_class = GPPLoginForm

    def perform_login_and_logout(self, **kwargs: Any) -> bool:
        """Perform GPP login check using a token.

        Parameters
        ----------
        **kwargs : Any
            Arbitrary keyword arguments. Must include:
            - token : str
                The authentication token to use for the GPP client.

        Returns
        -------
        bool
            `True` if the GPP endpoint is reachable and the token is valid, `False`
            otherwise.
        """
        token = kwargs.get("token")
        client = GPPClient(env=settings.GPP_ENV, token=token)

        try:
            is_reachable, error = async_to_sync(client.is_reachable)()
            if not is_reachable:
                logger.debug(f"GPP endpoint is not reachable: {error}")
                raise Exception(error)
        except Exception:
            return False
        return True
