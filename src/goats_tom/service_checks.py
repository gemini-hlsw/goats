"""Checks that an external service is up and accepts a user's credentials.

Shared by the credential forms, which verify before saving, and by the status
page, which verifies what is already saved.
"""

__all__ = [
    "CheckResult",
    "check_astro_datalab",
    "check_goa",
    "check_gpp",
    "check_gpp_reachable",
    "check_lco",
    "check_reachable",
]

import asyncio
import logging
from dataclasses import dataclass

import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient

from goats_tom.astro_data_lab import AstroDataLabClient
from goats_tom.astroquery import ObservationsClass

logger = logging.getLogger(__name__)

#: Seconds to wait on a service before calling it unreachable.
TIMEOUT = 10


@dataclass(frozen=True)
class CheckResult:
    """The outcome of a check.

    Parameters
    ----------
    ok : `bool`
        Whether the service answered and accepted the credentials.
    message : `str`
        What happened, for display.
    reachable : `bool`, optional
        Whether the service answered at all, so a failed check can tell
        rejected credentials from a service that is down.
    verified : `bool`, optional
        Whether authentication produced a conclusive result; `False` when
        a check fails inconclusively or the service offers no check.
    """

    ok: bool
    message: str
    reachable: bool = True
    verified: bool = True


def _failed(name: str, message: str, url: str, detail: object = None) -> CheckResult:
    """Classify a failure without inferring authentication from a public page.

    Parameters
    ----------
    name : `str`
        The service's name, for display.
    message : `str`
        What to show only when authentication was explicitly rejected.
    url : `str`
        A URL of the service that answers without signing in.
    detail : `object`, optional
        The underlying error, logged but never shown.

    Returns
    -------
    `CheckResult`
        The failure, marked unreachable if the server does not answer.
    """
    response = getattr(detail, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        status_code = getattr(detail, "status_code", None)
    # Never log exception text: request URLs may contain tokens.
    logger.info(
        "%s check failed (%s, HTTP %s)",
        name,
        type(detail).__name__,
        status_code if isinstance(status_code, int) else "unknown",
    )
    if isinstance(status_code, int) and status_code in (401, 403):
        return CheckResult(False, message)
    reachability = check_reachable(url, name)
    if not reachability.ok:
        return reachability
    # A working homepage says nothing about an API timeout, 5xx or rate limit.
    return CheckResult(
        False,
        f"The {name} credential check could not be completed. Please try again later.",
        verified=False,
    )


def check_gpp(token: str) -> CheckResult:
    """Check that GPP accepts a token.

    Parameters
    ----------
    token : `str`
        The GPP API token.

    Returns
    -------
    `CheckResult`
        The outcome.
    """

    async def probe() -> CheckResult:
        client = GPPClient(token=token, debug=False)
        try:
            # The public GraphQL client preserves HTTP errors; GPPClient.ping
            # turns them into strings and loses the authentication status.
            async with client.graphql as graphql:
                await asyncio.wait_for(graphql.ping(), timeout=TIMEOUT)
            return CheckResult(True, "GPP accepted the token.")
        finally:
            await client.close()

    try:
        return async_to_sync(probe)()
    except Exception as exc:
        # Use the configured endpoint, without constructing another client.
        from gpp_client.settings import GPPSettings  # noqa: PLC0415

        return _failed(
            "GPP",
            "GPP rejected the token.",
            GPPSettings().environment.base_url,
            exc,
        )


def check_gpp_reachable() -> CheckResult:
    """Check that GPP answers the client's ping query, without a token.

    Returns
    -------
    `CheckResult`
        The outcome. GPP refuses the query for want of a token, but a GraphQL
        error in its answer shows the service is up; the server's root and
        any GET answer 4xx, so they cannot tell.
    """
    from gpp_client.settings import GPPSettings  # noqa: PLC0415
    from gpp_client.urls import get_graphql_url  # noqa: PLC0415

    # The query `GPPClient.ping` sends, which the client will not send tokenless.
    query = "query ping { programs(LIMIT: 1) { matches { id } } }"
    try:
        response = requests.post(
            get_graphql_url(GPPSettings().environment),
            json={"query": query, "operationName": "ping"},
            timeout=TIMEOUT,
        )
        code = response.status_code
        answered = code < 500 and "errors" in response.json()
        up = 200 <= code < 300 or answered
        detail = f"HTTP {code}"
    except Exception as exc:
        up, detail = False, type(exc).__name__
    if not up:
        logger.info("GPP connectivity check failed (%s)", detail)
        return CheckResult(False, "GPP is not available.", reachable=False)
    return CheckResult(True, "GPP is available.")


def check_goa(username: str, password: str) -> CheckResult:
    """Check that GOA accepts a username and password.

    Parameters
    ----------
    username : `str`
        The GOA username.
    password : `str`
        The GOA password.

    Returns
    -------
    `CheckResult`
        The outcome.
    """
    # A private session: the shared `Observations` one may be in use elsewhere.
    goa = ObservationsClass()
    try:
        goa.login(username, password)
        if not goa.authenticated():
            if goa.login_rejected is True:
                return CheckResult(False, "GOA rejected the credentials.")
            return _failed(
                "GOA", "GOA rejected the credentials.", goa.url_helper.server
            )
        goa.logout()
        return CheckResult(True, "GOA accepted the credentials.")
    finally:
        goa._session.close()


def check_astro_datalab(username: str, password: str) -> CheckResult:
    """Check that Astro Data Lab accepts a username and password.

    Parameters
    ----------
    username : `str`
        The Astro Data Lab username.
    password : `str`
        The Astro Data Lab password.

    Returns
    -------
    `CheckResult`
        The outcome.
    """
    rejected = "Astro Data Lab rejected the credentials."
    with AstroDataLabClient(username=username, password=password) as client:
        url = client.config.base_url
        try:
            client.login()
            logged_in = client.is_logged_in()
        except Exception as exc:
            return _failed("Astro Data Lab", rejected, url, exc)
    if not logged_in:
        return CheckResult(False, rejected)
    return CheckResult(True, "Astro Data Lab accepted the credentials.")


def check_lco(token: str) -> CheckResult:
    """Check that the LCO portal accepts an API key.

    Parameters
    ----------
    token : `str`
        The LCO API key.

    Returns
    -------
    `CheckResult`
        The outcome.
    """
    url = settings.FACILITIES["LCO"]["portal_url"]
    try:
        response = requests.get(
            f"{url}/api/proposals/",
            headers={"Authorization": f"Token {token}"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        return _failed("LCO", "LCO rejected the API key.", url, exc)
    return CheckResult(True, "LCO accepted the API key.")


def check_reachable(
    url: str, name: str, headers: dict[str, str] | None = None
) -> CheckResult:
    """Check that a server answers at a URL, without signing in.

    Parameters
    ----------
    url : `str`
        The URL to request.
    name : `str`
        The service's name, for display.
    headers : `dict[str, str] | None`, optional
        Extra request headers, for a service that turns away unknown clients.

    Returns
    -------
    `CheckResult`
        A successful HTTP response confirms connectivity only. Client errors
        leave availability unknown; server and network failures are unavailable.
    """
    try:
        # Only the status code matters: do not download the page.
        response = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True)
        response.close()
        code = response.status_code
        if 400 <= code < 500:
            message = (
                f"{name} is limiting requests. Please try again later."
                if code == 429
                else f"{name} returned HTTP {code}; availability is not confirmed."
            )
            return CheckResult(False, message, verified=False)
        up = 200 <= code < 400
        detail = f"HTTP {code}"
    except Exception as exc:
        up, detail = False, type(exc).__name__
    if not up:
        logger.info("%s connectivity check failed (%s)", name, detail)
        return CheckResult(False, f"{name} is not available.", reachable=False)
    return CheckResult(True, f"{name} is available.")
