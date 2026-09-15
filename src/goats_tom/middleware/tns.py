"""
Middleware for per-request TNS credential injection.

Originally this answered one question -- "what are *my* TNS credentials?" --
because there was only one answer. With group sharing there can be several:
a user may hold their own bot and also have been granted posting rights on
other people's groups, and which one applies is a per-submission choice.

So the middleware now resolves an *option* rather than a login. The choice
itself is stored in the session under `SESSION_KEY`, set by
`goats_tom.views.tns_report`, and every resolution runs through
`goats_tom.tns_membership.resolve_posting_option`, which re-checks that the
user still holds what the session claims. Nothing here trusts the session
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

The session rather than a URL parameter, because `tom_tns` posts its forms
to its own submit endpoints (`tom_tns:submit-report`, `submit-classify`)
whose URLs GOATS does not construct -- a query parameter set on the page
would be dropped on the way to the very request that needs it.
"""


def build_payload(
    bot_id: str,
    bot_name: str,
    api_key: str,
    group_names: list[str],
    recommended_authors: str = "",
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
    recommended_authors : str, optional
        Author list to pre-fill on the report and classify forms. Surfaced
        through the patched ``tom_tns.tns_api.default_authors`` (see
        `goats_tom.apps`), which is the hook `tom_tns`'s own template tags
        already consult -- so carrying it here costs one key and needs no
        change to the upstream forms.

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
    `group_names` carries only the groups this option may file under.
    `tom_tns.forms` builds the "Reporting group" dropdown from whatever this
    returns, so for somebody else's bot that list is exactly the groups
    granted -- which is what keeps a grant on one group from widening to
    every group the owner's bot can reach. For the user's own bot it is
    their whole list, since that was always theirs to choose from.

    `recommended_authors` seeds the author field on first render and
    `group_authors` lets it follow the dropdown afterwards. Both are needed:
    the author list is a per-group setting, but the group is picked after
    the page has loaded.
    """
    login = getattr(option.owner, "tnslogin", None)
    if login is None:
        return None

    group_names = [group.name for group in option.groups]
    authors_by_group = option.group_authors
    # Seeded from the group that will be selected when the page first
    # renders, which is the first in the list.
    initial_authors = ""
    for name in group_names:
        if authors_by_group.get(name):
            initial_authors = authors_by_group[name]
            break

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
    """
    Attach the acting user's chosen TNS credentials to the request context.
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Intercept requests whose path starts with ``/tns/`` and set credentials.

        For any other path the middleware is a no-op to minimise overhead.
        """
        # Check if url is TNS, if not, don't bother.
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

    def _resolve_payload(
        self, request: HttpRequest, user
    ) -> dict[str, Any] | None:
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
            post -- in which case the context variable is left unset and
            `tom_tns` falls back to the settings-based credentials, exactly
            as it did before sharing existed.

        Notes
        -----
        Falls back to the user's own login if the membership machinery
        raises. That path exists for tests and for any caller constructing
        a bare request without a session; the original single-user
        behaviour is still correct there, and failing the request instead
        would break TNS for the common case over an edge one.
        """
        # Imported here rather than at module scope: `goats_tom.apps`
        # imports this module at startup, before the app registry is
        # ready, and `tns_membership` imports models.
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
            return build_payload(
                login.bot_id,
                login.bot_name,
                login.token,
                list(login.group_names or []),
            )

        return payload_for_option(option)
