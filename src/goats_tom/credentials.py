"""Reads the credentials a user has stored for an external service."""

__all__ = ["MissingCredentialsError", "get_credentials", "require_credentials"]

import logging
from typing import TYPE_CHECKING

from goats_tom.context.user_context import get_current_user_id

if TYPE_CHECKING:
    # Typing only: `django_dramatiq` imports this before the apps are loaded.
    from django.contrib.auth.models import AnonymousUser, User

    from goats_tom.models.logins.base import BaseLogin

logger = logging.getLogger(__name__)


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
