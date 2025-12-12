"""
Make Dramatiq Abortable middleware available and configured.
"""

__all__ = ["setup_dramatiq_abort"]

import logging

logger = logging.getLogger(__name__)


def setup_dramatiq_abort() -> None:
    """
    Configure Dramatiq Abortable middleware with Redis backend.
    """
    from django.conf import settings  # noqa: PLC0415
    from dramatiq import get_broker  # noqa: PLC0415
    from dramatiq_abort import Abortable, backends  # noqa: PLC0415

    event_backend = backends.RedisBackend.from_url(settings.DRAMATIQ_REDIS_URL)
    middleware = Abortable(backend=event_backend)
    get_broker().add_middleware(middleware)

    logger.debug("Dramatiq Abortable middleware installed")
