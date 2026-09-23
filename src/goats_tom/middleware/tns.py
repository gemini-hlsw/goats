"""
Middleware for per-request TNS credential injection.
"""

__all__ = ["TNSCredentialsMiddleware"]

import contextvars
import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from goats_tom.credentials import get_credentials

# Context-local store for the current request’s creds.
current_tns_creds = contextvars.ContextVar("current_tns_creds", default=None)


def build_payload(
    bot_id: str, bot_name: str, api_key: str, group_names: list[str]
) -> dict[str, Any]:
    """
    Build the dict returned by ``tom-tns``'s credential helper.

    Parameters
    ----------
    bot_id : str
        Bot identifier assigned by TNS.
    bot_name : str
        Human-readable bot name registered with TNS.
    api_key : str
        API key issued by TNS for the bot.
    group_names : list[str]
        Names of TNS user groups that the bot should post to.

    Returns
    -------
    dict[str, Any]
        A mapping that matches the structure expected by
        ``tom_tns.tns_api.get_tns_credentials``.
    """
    base_url = settings.BROKERS.get("TNS", {}).get(
        "tns_base_url", "https://www.wis-tns.org/"
    )
    return {
        "bot_id": bot_id,
        "bot_name": bot_name,
        "api_key": api_key,
        "group_names": group_names,
        "tns_base_url": base_url,
        "marker": "tns_marker"
        + json.dumps({"tns_id": bot_id, "type": "bot", "name": bot_name}),
    }


class TNSCredentialsMiddleware(MiddlewareMixin):
    """
    Attach a user's TNS credentials to the request context.
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Intercept requests whose path starts with ``/tns/`` and set credentials.

        For any other path the middleware is a no-op to minimise overhead.
        """
        # Check if url is TNS, if not, don't bother.
        if not request.path.startswith("/tns/"):
            return self.get_response(request)
        # Imported here: `django_dramatiq` loads this package before the apps.
        from goats_tom.models import TNSLogin  # noqa: PLC0415

        token = None
        login = get_credentials(TNSLogin, user=getattr(request, "user", None))
        if login is not None:
            token = current_tns_creds.set(
                build_payload(
                    login.bot_id,
                    login.bot_name,
                    login.token,
                    login.group_names,
                )
            )
        try:
            return self.get_response(request)
        finally:
            if token is not None:
                current_tns_creds.reset(token)
