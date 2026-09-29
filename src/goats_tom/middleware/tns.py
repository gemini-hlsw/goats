"""Middleware for per-request TNS credential injection.

With group sharing a user may hold several ways to post, so this resolves an
*option* rather than a login. The choice is stored in the session under
`SESSION_KEY` and every resolution runs through
`goats_tom.tns_membership.resolve_posting_option`, which re-checks that the
user still holds what the session claims -- nothing here trusts the session
value beyond using it as a lookup key.
"""

__all__ = [
    "TNSCredentialsMiddleware",
    "SESSION_KEY",
    "build_payload",
    "payload_for_option",
    "current_tns_creds",
]

import contextvars
import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Context-local store for the current request's creds.
current_tns_creds = contextvars.ContextVar("current_tns_creds", default=None)

SESSION_KEY = "tns_posting_option"
"""Session key holding the user's chosen `PostingOption.key`.

The session rather than a URL parameter: `tom_tns` posts to its own submit
endpoints, whose URLs GOATS does not construct, so a query parameter would
be dropped on the way to the request that needs it.
"""


def build_payload(
    bot_id: str,
    bot_name: str,
    api_key: str,
    group_names: list[str],
    recommended_authors: str = "",
) -> dict[str, Any]:
    """Build the dict returned by ``tom-tns``'s credential helper.

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
    recommended_authors : str, optional
        Author list to pre-fill on the report and classify forms, surfaced
        through the patched ``tom_tns.tns_api.default_authors``.

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
        "recommended_authors": recommended_authors,
        "tns_base_url": base_url,
        "marker": "tns_marker"
        + json.dumps({"tns_id": bot_id, "type": "bot", "name": bot_name}),
    }


def payload_for_option(option) -> dict[str, Any] | None:
    """Build the credential payload for one resolved posting option.

    Parameters
    ----------
    option : `goats_tom.tns_membership.PostingOption`
        The option the acting user selected and still holds.

    Returns
    -------
    dict or None
        `None` if the option's owner has no credentials stored, which can
        happen between a grant and the owner deleting their bot.

    Notes
    -----
    `group_names` carries only the groups this option may file under, and
    `tom_tns.forms` builds the "Reporting group" dropdown from it -- which is
    what keeps a grant on one group from widening to every group the owner's
    bot can reach. `recommended_authors` seeds the author field on first
    render; `group_authors` lets it follow the dropdown afterwards.
    """
    login = getattr(option.owner, "tnslogin", None)
    if login is None:
        return None

    group_names = [group.name for group in option.groups]
    authors_by_group = option.group_authors
    # The group the page renders selected, which is the first: `tom_tns`
    # gives `reporting_group` no initial, so the browser takes option one.
    # Seeding from any other group would caption it with the wrong authors.
    initial_authors = authors_by_group.get(group_names[0], "") if group_names else ""

    payload = build_payload(
        login.bot_id,
        login.bot_name,
        login.token,
        group_names,
        recommended_authors=initial_authors,
    )
    payload["group_authors"] = authors_by_group
    return payload


class TNSCredentialsMiddleware(MiddlewareMixin):
    """Attach the acting user's chosen TNS credentials to the request context."""

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Set credentials on ``/tns/`` requests, and no-op on every other path."""
        if not request.path.startswith("/tns/"):
            return self.get_response(request)

        token = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            payload = self._resolve_payload(request, user)
            if payload is not None:
                token = current_tns_creds.set(payload)
        try:
            return self.get_response(request)
        finally:
            if token is not None:
                current_tns_creds.reset(token)

    def _resolve_payload(self, request: HttpRequest, user) -> dict[str, Any] | None:
        """Work out which credentials this request should use.

        Parameters
        ----------
        request : `HttpRequest`
            The current request; its session holds the chosen option key.
        user : `django.contrib.auth.models.User`
            The acting user.

        Returns
        -------
        dict or None
            The credential payload, or `None` if the user has no way to
            post, leaving the context variable unset so `tom_tns` falls back
            to the settings-based credentials.

        Notes
        -----
        Falls back to the user's own login if the membership machinery
        raises, which covers callers constructing a bare request without a
        session; failing the request would break the common case over an
        edge one.
        """
        # Imported here because `goats_tom.apps` imports this module before
        # the app registry is ready, and `tns_membership` imports models.
        from goats_tom.tns_membership import (  # noqa: PLC0415
            resolve_posting_option,
        )

        session = getattr(request, "session", None)
        key = session.get(SESSION_KEY) if session is not None else None

        try:
            option = resolve_posting_option(user, key)
        except Exception:
            logger.exception(
                "Could not resolve TNS posting option for %s; falling back "
                "to their own credentials.",
                getattr(user, "username", None),
            )
            option = None

        if option is None:
            login = getattr(user, "tnslogin", None)
            if login is None:
                return None
            # Read off the group rows, which are what the owner edits.
            from goats_tom.tns_membership import owned_groups  # noqa: PLC0415

            return build_payload(
                login.bot_id,
                login.bot_name,
                login.token,
                [group.name for group in owned_groups(user)],
            )

        return payload_for_option(option)
