"""
User-scoped cache context middleware.

This middleware stores the authenticated user's ID in a request-scoped context
for specific request paths so cache key functions can vary keys per user.
"""

import logging
import re
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from goats_tom.cache.user_context import user_id_context

__all__ = ["UserScopedCacheMiddleware"]

logger = logging.getLogger(__name__)

_CREATE_PATH = re.compile(r"^/observations/(?!GEM/)[^/]+/create/?$")


class UserScopedCacheMiddleware:
    """
    Persist the authenticated user ID for the duration of a request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Set the authenticated user ID in the cache context for matching requests.

        For non-matching paths, the middleware is a no-op to minimize overhead.
        """
        if not _CREATE_PATH.match(request.path):
            logger.debug(
                "UserScopedCacheMiddleware: path does not match create pattern: %s",
                request.path,
            )
            return self.get_response(request)

        uid = self._get_user_id(request)
        logger.debug(
            "UserScopedCacheMiddleware: entering user context (uid=%s) for path=%s",
            uid,
            request.path,
        )

        with user_id_context(uid):
            try:
                return self.get_response(request)
            finally:
                logger.debug(
                    "UserScopedCacheMiddleware: exiting user context for path=%s",
                    request.path,
                )

    @staticmethod
    def _get_user_id(request: HttpRequest) -> int | None:
        """
        Extract the authenticated user ID from a request.

        Parameters
        ----------
        request : HttpRequest
            The incoming Django request.

        Returns
        -------
        int | None
            The authenticated user's ID, or ``None`` if the request is anonymous
            or the request does not have a ``user`` attribute.
        """
        user = getattr(request, "user", None)
        return (
            getattr(user, "id", None)
            if getattr(user, "is_authenticated", False)
            else None
        )
