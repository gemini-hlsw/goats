__all__ = [
    "BaseStatusMixin",
    "Credentials",
    "Status",
    "StatusPayload",
    "MissingCredentialsError",
    "register_status",
    "status_mixins",
]

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from django.core.cache import cache
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

# Re-exported: defined with the lookup that raises it, imported from here.
from goats_tom.credentials import MissingCredentialsError
from goats_tom.service_checks import CheckResult, check_reachable

logger = logging.getLogger(__name__)

status_mixins: dict[str, dict[str, Any]] = {}

#: Seconds a check made with a user's credentials is reused, so reloading the
#: page does not sign in to every service each time.
CACHE_SECONDS = 60


class Status(str, Enum):
    """
    Whether a service is available.
    """

    OK = "ok"
    DOWN = "down"
    UNKNOWN = "unknown"


class Credentials(str, Enum):
    """
    What happened to the user's stored credentials for a service.
    """

    VERIFIED = "verified"
    REJECTED = "rejected"
    MISSING = "missing"
    UNVERIFIABLE = "unverifiable"
    UNCHECKED = "unchecked"


@dataclass
class StatusPayload:
    """
    Represents the payload for a service status response.

    `credentials` is `None` for a service used without credentials.
    """

    name: str
    status: str
    credentials: str | None
    message: str
    latency_ms: float
    timestamp: str


def register_status(
    name: str,
    display_name: str,
    *,
    url: str | None = None,
    url_label: str | None = None,
    manage_url_name: str | None = None,
):
    """
    Registers a status mixin under a given service name for the status endpoint.

    This decorator associates a service-specific status check class with a unique
    service name and its display label, allowing dynamic dispatch by the
    `StatusViewSet` at the route `/api/status/<name>/`.

    The decorated class must inherit from `BaseStatusMixin`, and implement
    `check_service` and optionally `get_credentials`.

    This decorator also stores metadata used for documentation or UI purposes.

    Parameters
    ----------
    name : str
        The machine-readable service name (used in the URL path, e.g., "gpp").
    display_name : str
        A human-readable label for display (e.g., "Gemini Program Platform").
    url : str | None, optional
        The service's website, linked from the page. Defaults to the mixin's
        `get_public_url`.
    url_label : str | None, optional
        The name of the site `url` opens, when it is not the service itself.
    manage_url_name : str | None, optional
        The URL name of the page that manages the user's credentials for it.

    Returns
    -------
    Callable
        A class decorator that registers the mixin in the global `status_mixins`
        registry.

    Raises
    ------
    ValueError
        If a service with the given name is already registered.
    """

    def decorator(cls: type) -> type:
        if name in status_mixins:
            logger.exception(f"Service '{name}' is already registered.")
            raise ValueError(f"Service '{name}' is already registered.")
        status_mixins[name] = {
            "instance": cls(),
            "display_name": display_name,
            "endpoint": f"/status/{name}/",
            "group": "account" if cls.uses_credentials else "public",
            "url": url,
            "url_label": url_label,
            "manage_url_name": manage_url_name,
        }
        logger.info(f"Registered status for service '{name}'.")
        return cls

    return decorator


class BaseStatusMixin:
    service_name: str = "Unnamed Service"
    #: Whether the check signs in with the user's credentials.
    uses_credentials: bool = True

    def get_credentials(self, request: Request) -> dict:
        """
        Retrieves the credentials from the request.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            A dictionary of credentials.

        Raises
        ------
        MissingCredentialsError
            If credentials are missing.
        """
        return {}

    def get_public_url(self) -> str | None:
        """
        Returns a URL that shows whether the service is up without signing in.

        Returns
        -------
        str | None
            The URL, or `None` if the service offers none. Read when checking,
            so settings apply.
        """
        return None

    def get_public_headers(self) -> dict[str, str]:
        """
        Returns headers the service needs to answer `get_public_url`.

        Returns
        -------
        dict[str, str]
            The headers; none by default.
        """
        return {}

    def check_public(self) -> CheckResult | None:
        """
        Checks whether the service is available, without credentials.

        Returns
        -------
        CheckResult | None
            The outcome, or `None` if the service offers no way to tell.
        """
        url = self.get_public_url()
        if url is None:
            return None
        return check_reachable(url, self.service_name, self.get_public_headers())

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks the service using the provided credentials.

        Parameters
        ----------
        credentials : dict
            A dictionary of credentials.

        Returns
        -------
        CheckResult
            The outcome of the check.

        Raises
        ------
        NotImplementedError
            If the method is not implemented by a subclass.
        """
        raise NotImplementedError("Subclasses must implement 'check_service'.")

    def get(self, request, *args, **kwargs) -> Response:
        """
        Handles the GET request to check the service status.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        Response
            A response containing the service status payload.
        """
        start_time = datetime.now(timezone.utc)
        return_status = status.HTTP_200_OK

        cache_key = None
        try:
            try:
                credentials = self.get_credentials(request)
                missing = False
            except MissingCredentialsError:
                credentials = {"missing": True}
                missing = True
            cache_key = self._cache_key(request, credentials)
            if cache_key and request.query_params.get("refresh") != "1":
                cached = cache.get(cache_key)
                if cached is not None:
                    return Response(cached, status=return_status)
            state = (
                self._missing_state()
                if missing
                else self._result_state(self.check_service(credentials))
            )
        except Exception:
            # Unexpected client errors can include secrets in their text.
            logger.warning("%s status check failed.", self.service_name)
            state = (
                Status.UNKNOWN,
                Credentials.UNCHECKED if self.uses_credentials else None,
                f"{self.service_name} could not be checked.",
            )

        service_status, credentials_state, message = state
        # Calculate latency.
        latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        payload = asdict(
            StatusPayload(
                name=self.service_name,
                status=service_status.value,
                credentials=credentials_state.value if credentials_state else None,
                message=message,
                latency_ms=round(latency_ms, 2),
                timestamp=start_time.isoformat(),
            )
        )
        if cache_key:
            cache.set(cache_key, payload, CACHE_SECONDS)
        return Response(payload, status=return_status)

    def _missing_state(self) -> tuple[Status, Credentials, str]:
        """
        Returns the state of a service the user has stored no credentials for.

        Returns
        -------
        tuple[Status, Credentials, str]
            Whether the service is available (checked without signing in, if it
            can be), `Credentials.MISSING`, and a message.
        """
        result = self.check_public()
        if result is None:
            return Status.UNKNOWN, Credentials.MISSING, "No credentials stored."
        if not result.ok:
            state = Status.DOWN if result.reachable is False else Status.UNKNOWN
            return state, Credentials.MISSING, result.message
        return Status.OK, Credentials.MISSING, "No credentials stored."

    def _result_state(
        self, result: CheckResult
    ) -> tuple[Status, Credentials | None, str]:
        """
        Splits a check's outcome into availability and credentials state.

        Parameters
        ----------
        result : CheckResult
            The outcome of the check.

        Returns
        -------
        tuple[Status, Credentials | None, str]
            Whether the service is available, what happened to the credentials
            (`None` if the service uses none), and the check's message.
        """
        service_status = {True: Status.OK, False: Status.DOWN}.get(
            result.reachable, Status.UNKNOWN
        )
        if not self.uses_credentials:
            if result.reachable and not result.ok:
                service_status = Status.UNKNOWN
            return service_status, None, result.message
        if not result.reachable:
            credentials_state = Credentials.UNCHECKED
        elif not result.ok:
            # A service that is up but did not finish the credential check is
            # still available; only the credentials stay unchecked.
            credentials_state = (
                Credentials.REJECTED if result.verified else Credentials.UNCHECKED
            )
        elif not result.verified:
            credentials_state = Credentials.UNVERIFIABLE
        else:
            credentials_state = Credentials.VERIFIED
        return service_status, credentials_state, result.message

    def _cache_key(self, request: Request, credentials: dict) -> str | None:
        """
        Returns the cache key for a check made with a user's credentials.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.
        credentials : dict
            The credentials the check is made with.

        Returns
        -------
        str | None
            The key, or `None` if there is no signed-in user. Public checks and
            missing credentials are cached too. Changing credentials or the
            configured endpoint changes the key.
        """
        user_pk = getattr(request.user, "pk", None)
        if not isinstance(user_pk, int):
            return None
        digest = hashlib.sha256(
            json.dumps(
                {"credentials": credentials, "endpoint": self.get_public_url()},
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        return f"goats:status:{type(self).__name__}:{user_pk}:{digest}"
