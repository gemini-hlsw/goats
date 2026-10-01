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
from collections.abc import Callable
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


def _failed(
    name: str,
    message: str,
    reachable: Callable[[], CheckResult],
    detail: object = None,
    server_error: str | None = None,
) -> CheckResult:
    """Classify a failure without inferring authentication from a public page.

    Parameters
    ----------
    name : `str`
        The service's name, for display.
    message : `str`
        What to show only when authentication was explicitly rejected.
    reachable : `Callable[[], CheckResult]`
        Checks, without signing in, whether the service is up.
    detail : `object`, optional
        The underlying error, logged but never shown.
    server_error : `str | None`, optional
        What to show when the service is up but fails on the credentials.

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
    reachability = reachable()
    if not reachability.ok:
        return reachability
    # The service is up, so the failure is specific to the credential check.
    if status_code == 429:
        reason = f"{name} is limiting requests. Please try again in a few minutes."
    elif isinstance(detail, (TimeoutError, requests.Timeout)):
        reason = f"{name} took too long to check the credentials. Please try again."
    elif isinstance(status_code, int) and status_code >= 500:
        reason = server_error or (
            f"{name} had an internal error while checking the credentials. "
            "Please try again later."
        )
    else:
        reason = f"{name} is available but did not complete the credential check."
    return CheckResult(False, reason, verified=False)


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
        from gpp_client.settings import GPPEnvironment, GPPSettings  # noqa: PLC0415

        # GPP answers without a token yet fails with this one: a token created
        # in another GPP environment gets a server error, not a rejection.
        server_error = "GPP could not validate the token."
        if GPPSettings().environment != GPPEnvironment.PRODUCTION:
            # Only developers switch environments; production users need no hint.
            server_error += (
                " GOATS is using GPP Development; the token may be from Production."
            )
        return _failed(
            "GPP",
            "GPP rejected the token.",
            check_gpp_reachable,
            exc,
            server_error=server_error,
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
            server = goa.url_helper.server
            return _failed(
                "GOA",
                "GOA rejected the credentials.",
                lambda: check_reachable(server, "GOA"),
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
            return _failed(
                "Astro Data Lab",
                rejected,
                lambda: check_reachable(url, "Astro Data Lab"),
                exc,
            )
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
        return _failed(
            "LCO",
            "LCO rejected the API key.",
            lambda: check_reachable(url, "LCO"),
            exc,
        )
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
            if code == 429:
                message = (
                    f"{name} is limiting requests. Please try again in a few minutes."
                )
            elif code in (401, 403):
                message = f"{name} is refusing requests from GOATS."
            elif code == 404:
                message = f"The {name} address GOATS checks no longer exists."
            else:
                message = f"{name} did not accept the request GOATS sends to check it."
            logger.info("%s connectivity check inconclusive (HTTP %s)", name, code)
            return CheckResult(False, message, verified=False)
        up = 200 <= code < 400
        detail = f"HTTP {code}"
    except Exception as exc:
        up, detail = False, type(exc).__name__
    if not up:
        logger.info("%s connectivity check failed (%s)", name, detail)
        return CheckResult(False, f"{name} is not available.", reachable=False)
    return CheckResult(True, f"{name} is available.")
