"""Reads the credentials a user has stored for an external service."""

__all__ = [
    "CREDENTIAL_SERVICES",
    "MissingCredentialsError",
    "get_credential_status",
    "get_credentials",
    "get_service_label",
    "require_credentials",
]

import logging
from typing import TYPE_CHECKING, Any

from goats_tom.context.user_context import get_current_user_id

if TYPE_CHECKING:
    # Typing only: `django_dramatiq` imports this before the apps are loaded.
    from django.contrib.auth.models import AnonymousUser, User

    from goats_tom.models.logins.base import BaseLogin

logger = logging.getLogger(__name__)


#: Every service a user can store credentials for, as the pages list them:
#: the label shown, the URL that manages it, and the model it is stored in.
#: Models are named rather than imported: this module is loaded before the
#: app registry is ready.
CREDENTIAL_SERVICES = (
    ("Gemini Observatory Archive", "user-goa-login", "GOALogin"),
    ("Astro Data Lab", "user-astro-data-lab-login", "AstroDatalabLogin"),
    ("Gemini Program Platform", "user-gpp-login", "GPPLogin"),
    ("Las Cumbres Observatory", "user-lco-login", "LCOLogin"),
    ("Transient Name Server", "user-tns-login", "TNSLogin"),
)


class MissingCredentialsError(Exception):
    """Raised when required credentials are missing."""


def get_credentials(
    model: "type[BaseLogin]",
    *,
    user: "User | AnonymousUser | None" = None,
) -> "BaseLogin | None":
    """Return the credentials stored for a service, or `None` if there are none.

    Parameters
    ----------
    model : `type[BaseLogin]`
        The credential model to read, e.g. `GOALogin`.
    user : `User | AnonymousUser | None`, optional
        Whose credentials to read, by default the user of the current request
        or background task.

    Returns
    -------
    `BaseLogin | None`
        The stored credentials, or `None` if there are none to read.
    """
    if user is not None:
        # `related_name="%(class)s"` names the accessor after the model.
        return getattr(user, model._meta.model_name, None)

    uid = get_current_user_id()
    if uid is None:
        return None

    return model.objects.filter(user_id=uid).first()


def require_credentials(
    model: "type[BaseLogin]",
    *,
    user: "User | AnonymousUser | None" = None,
) -> "BaseLogin":
    """Return the credentials stored for a service, raising if there are none.

    Parameters
    ----------
    model : `type[BaseLogin]`
        The credential model to read, e.g. `GOALogin`.
    user : `User | AnonymousUser | None`, optional
        Whose credentials to read, by default the user of the current request
        or background task.

    Returns
    -------
    `BaseLogin`
        The stored credentials.

    Raises
    ------
    `MissingCredentialsError`
        If the user has no credentials stored for this service.
    """
    credentials = get_credentials(model, user=user)
    if credentials is None:
        raise MissingCredentialsError(
            f"No {model.__name__} credentials for the current user."
        )
    return credentials


def get_credential_status(
    user: "User", current_url_name: str | None = None
) -> list[dict[str, Any]]:
    """Return every service with whether the user has credentials stored for it.

    Parameters
    ----------
    user : `User`
        Whose stored credentials to report on.
    current_url_name : `str | None`, optional
        The URL being served, so a page listing the services can tell which
        one the reader is already on.

    Returns
    -------
    `list[dict[str, Any]]`
        One entry per service in `CREDENTIAL_SERVICES`, with its `label`, the
        `url_name` that manages it, whether anything is `stored`, and whether
        it `is_current`.
    """
    from goats_tom import models  # noqa: PLC0415

    return [
        {
            "label": label,
            "url_name": url_name,
            "stored": get_credentials(getattr(models, model_name), user=user)
            is not None,
            "is_current": url_name == current_url_name,
        }
        for label, url_name, model_name in CREDENTIAL_SERVICES
    ]


def get_service_label(url_name: str) -> str | None:
    """Returns the label of the service managed at a URL, if it is one.

    Parameters
    ----------
    url_name : `str`
        The name of the URL pattern being served.

    Returns
    -------
    `str | None`
        The service's label, or `None` if that URL manages no service.
    """
    for label, name, _ in CREDENTIAL_SERVICES:
        if name == url_name:
            return label
    return None
