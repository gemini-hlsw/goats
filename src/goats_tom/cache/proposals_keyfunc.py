"""Cache KEY_FUNCTION for user-scoped proposal and instrument keys."""

from __future__ import annotations

import logging

from django.core.cache.backends.base import default_key_func

from .user_context import get_current_user_id

__all__ = ["user_scoped_proposals_key"]

logger = logging.getLogger(__name__)


def user_scoped_proposals_key(key: str, key_prefix: str, version: int) -> str:
    """
    Rewrite selected cache keys to include the current authenticated user ID.

    This key function scopes specific cache entries per user by appending a user
    suffix (``:u<uid>``) before delegating to Django's ``default_key_func``.

    Parameters
    ----------
    key : str
        The cache key provided by the caller.
    key_prefix : str
        The cache key prefix configured for the backend.
    version : int
        The cache version.

    Returns
    -------
    str
        The final cache key returned by Django's default key function.
    """
    uid = get_current_user_id()

    if uid is None:
        logger.debug("No user in context; leaving cache key unchanged: %s", key)
        return default_key_func(key, key_prefix, version)

    if ("_proposals" or "instruments") not in key:
        return default_key_func(key, key_prefix, version)

    new_key = f"{key}:u{uid}"
    return default_key_func(new_key, key_prefix, version)
