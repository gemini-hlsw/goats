"""
Request-scoped user context middleware (ASGI-safe).

Stores the authenticated user ID in a ContextVar for the duration of every
request so downstream code can retrieve per-user credentials without having
to pass request/user objects around.
"""

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from goats_tom.context.user_context import user_id_context

__all__ = ["UserContextMiddleware"]

logger = logging.getLogger(__name__)


class UserContextMiddleware:
    """
    Persist the authenticated user ID for the duration of a request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        uid = user.id if getattr(user, "is_authenticated", False) else None

        logger.debug("UserContextMiddleware: uid=%s path=%s", uid, request.path)

        with user_id_context(uid):
            return self.get_response(request)
