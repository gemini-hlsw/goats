"""
Periodic task to check for the latest GOATS version and update the cache.
"""

__all__ = ["check_version"]

import logging
import uuid

import dramatiq
from django.core.cache import caches

from goats_common import VersionChecker
from goats_scheduler.scheduling import cron
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)

CACHE_KEY = "version_info"
LOCK_KEY = "lock:version_info"


@cron(second="*/30")  # Every 30 seconds for testing.
@dramatiq.actor
def check_version() -> None:
    """
    Periodic task to check for the latest GOATS version and update the cache.
    """

    version_checker = VersionChecker()
    result = version_checker.as_dict()

    if result["status"] != "success":
        # Do not update cache if there was an error checking versions.
        if result.get("errors") is not None:
            errors_str = "; ".join(result.get("errors", []))
            logger.warning("Version check failed: %s", errors_str)
        else:
            logger.warning("Version check failed with unknown error.")
        return

    # Store the result in the cache.
    _update_cache(result)


def _update_cache(result: dict[str, str | None | bool | list[str]]) -> None:
    """
    Update the version info cache in Redis with locking.

    Parameters
    ----------
    result : dict[str, str | None | bool | list[str]]
        The version information to store in the cache.
    """
    cache = caches["redis"]
    owner_id = str(uuid.uuid4())

    # Create a lock.
    if not cache.add(LOCK_KEY, owner_id, timeout=60):
        # Lock is in use, exit early.
        return
    try:
        previous = cache.get(CACHE_KEY, default={})

        # Only update cache if the result has changed.
        snapshot = {
            "current": result["current"],
            "latest": result["latest"],
            "is_outdated": result["is_outdated"],
        }
        if previous != snapshot:
            cache.set(CACHE_KEY, snapshot, timeout=None)
            logger.info("Version info cache updated.")
            # Send notification about the update if only if outdated.
            if snapshot["is_outdated"]:
                _send_notification(snapshot)

    finally:
        # Release the lock if we own it.
        if cache.get(LOCK_KEY) == owner_id:
            cache.delete(LOCK_KEY)


def _send_notification(result: dict[str, str | None | bool | list[str]]) -> None:
    """
    Send a WebSocket notification with the version information.

    Parameters
    ----------
    result : dict[str, str | None | bool | list[str]]
        The version information to send.
    """

    current = result["current"]
    latest = result["latest"]

    message = (
        f"A new version of GOATS is available: "
        f"<code>{latest}</code> (currently running <code>{current}</code>).<br><br>"
        f"<ol>"
        f"<li>Stop GOATS</li>"
        f"<li>Run <code>conda update goats</code></li>"
        f"<li>Start GOATS again</li>"
        f"</ol>"
    )

    NotificationInstance.create_and_send(
        label=f"GOATS Update Available: {latest}",
        message=message,
        color="warning",
        autohide=False,
    )
