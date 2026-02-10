"""Request-scoped user context utilities (ASGI-safe).
Helpers to store and retrieve the current authenticated user's ID in a
``ContextVar`` during the processing of a single request.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

__all__ = ["set_current_user_id", "get_current_user_id", "user_id_context"]

logger = logging.getLogger(__name__)

# ASGI-safe, request-scoped user id store.
_user_id_var: ContextVar[int | None] = ContextVar("current_user_id", default=None)


def set_current_user_id(uid: int | None) -> Token[int | None]:
    """Set the current request's authenticated user ID.
    Parameters
    ----------
    uid : int | None
        The authenticated user's ID, or ``None`` if unauthenticated.
    Returns
    -------
    Token[int | None]
        Token representing the previous state. Use ``_user_id_var.reset(token)``
        to restore it if needed.
    """
    prev = _user_id_var.get()
    token = _user_id_var.set(uid)
    logger.debug("Set current_user_id: %s -> %s", prev, uid)
    return token


def get_current_user_id() -> int | None:
    """Get the current request's authenticated user ID.
    Returns
    -------
    int | None
        The user ID stored for this request context, or ``None`` if unset.
    """
    return _user_id_var.get()


@contextmanager
def user_id_context(uid: int | None) -> Iterator[None]:
    """Temporarily set the current user ID and automatically restore it.
    Parameters
    ----------
    uid : int | None
        The user ID to set for the duration of the context.
    Yields
    ------
    None
        Yields control while the user ID is set, and restores the previous value
        on exit.
    """
    prev = _user_id_var.get()
    token = _user_id_var.set(uid)
    logger.debug("Enter user_id_context: %s -> %s", prev, uid)
    try:
        yield
    finally:
        _user_id_var.reset(token)
        logger.debug("Exit user_id_context: restored to %s", prev)
