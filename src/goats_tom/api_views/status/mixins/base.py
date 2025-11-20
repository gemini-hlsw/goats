__all__ = [
    "BaseStatusMixin",
    "Status",
    "StatusPayload",
    "MissingCredentialsError",
    "register_status",
    "status_mixins",
]

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)

status_mixins: dict[str, dict[str, Any]] = {}


class Status(str, Enum):
    """
    Represents the status of a service.
    """

    OK = "ok"
    WARNING = "warning"
    DOWN = "down"


@dataclass
class StatusPayload:
    """
    Represents the payload for a service status response.
    """

    name: str
    status: str
    message: str
    latency_ms: float
    timestamp: str


class MissingCredentialsError(Exception):
    """Raised when required credentials are missing."""


def register_status(name: str, display_name: str):
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
        }
        logger.info(f"Registered status for service '{name}'.")
        return cls

    return decorator


class BaseStatusMixin:
    service_name: str = "Unnamed Service"

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

    def check_service(self, credentials: dict, *args, **kwargs) -> tuple[Status, str]:
        """
        Checks the status of the service using the provided credentials.

        Parameters
        ----------
        credentials : dict
            A dictionary of credentials.

        Returns
        -------
        tuple[Status, str]
            A tuple containing the service status and a message.

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

        try:
            credentials = self.get_credentials(request)
        except MissingCredentialsError:
            payload = StatusPayload(
                name=self.service_name,
                status=Status.WARNING.value,
                message=f"Missing credentials for {self.service_name}",
                latency_ms=0.0,
                timestamp=start_time.isoformat(),
            )
            return Response(asdict(payload), status=return_status)

        try:
            status_enum, message = self.check_service(credentials)
        except Exception as exc:
            status_enum = Status.DOWN
            message = str(exc)

        # Calculate latency.
        latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        payload = StatusPayload(
            name=self.service_name,
            status=status_enum.value,
            message=message,
            latency_ms=round(latency_ms, 2),
            timestamp=start_time.isoformat(),
        )
        return Response(asdict(payload), status=return_status)
