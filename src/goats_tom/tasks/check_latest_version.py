"""Check and publish the latest GOATS version info (WS + Redis cache)."""

__all__ = ["check_version_info"]

import logging
from importlib.metadata import version as get_version
from json import JSONDecodeError

import dramatiq
import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import caches
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

PACKAGE_NAME = "goats"
CHANNELDATA_URL = "https://gemini-hlsw.github.io/goats-infra/conda/channeldata.json"
GROUP_NAME = "updates_group"
CACHE_KEY = "version:info"


def _notify_version_info_ws(is_outdated: bool, current: str, latest: str) -> None:
    """Push a version snapshot to the ``updates_group`` WebSocket group.

    Sends a Django Channels group message with ``type="version.info"`` that
    includes whether the installed version is outdated and the current/latest
    version strings.

    Parameters
    ----------
    is_outdated : bool
        ``True`` if the installed version is older than the latest available.
    current : str
        Installed package version string.
    latest : str
        Latest available package version string resolved from the channel.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not available; skipping WS push.")
            return
        payload = {
            "type": "version.info",
            "is_outdated": is_outdated,
            "current": current,
            "latest": latest,
        }
        async_to_sync(channel_layer.group_send)(GROUP_NAME, payload)
    except Exception as e:
        logger.warning("WS push failed: %s", e)


def _update_info(is_outdated: bool, current: str, latest: str) -> None:
    """
    Persist the snapshot in Redis (Django cache) and emit WS if it changed.

    Parameters
    ----------
    is_outdated : bool
        Outdated flag.
    current : str
        Installed version.
    latest : str
        Latest available version.
    """
    cache = caches["redis"]

    if not cache.add("lock:version-info", 1, timeout=60):
        return
    try:
        prev = cache.get(CACHE_KEY) or {}
        snap = {"is_outdated": is_outdated, "current": current, "latest": latest}
        if snap != prev:
            cache.set(CACHE_KEY, snap, timeout=None)
            _notify_version_info_ws(is_outdated, current, latest)
    finally:
        cache.delete("lock:version-info")


@dramatiq.actor
def check_version_info(timeout_sec: int = 5) -> None:
    """Compute installed vs. latest ``goats`` version and broadcast via WebSocket.

    Retrieves channel metadata from ``CHANNELDATA_URL``, compares the installed
    version with the latest available, and emits a Channels group message with
    ``type="version.info"`` to ``updates_group`` containing the fields
    ``is_outdated``, ``current``, and ``latest``.

    Parameters
    ----------
    timeout_sec : int, optional
        HTTP timeout (in seconds) for fetching the channel metadata. Defaults to ``5``.
    """
    current = get_version(PACKAGE_NAME).strip()

    latest = ""
    is_outdated = False

    try:
        resp = requests.get(CHANNELDATA_URL, timeout=timeout_sec)
        resp.raise_for_status()
        data = resp.json()
        latest = (data["packages"][PACKAGE_NAME]["version"] or "").strip()
    except requests.Timeout as e:
        logger.warning("Timed out fetching channel metadata: %s", e)
        return
    except requests.RequestException as e:
        logger.warning("Failed to fetch latest version info: %s", e)
        return
    except (JSONDecodeError, ValueError) as e:
        logger.error("Invalid JSON from channel: %s", e)
        return
    except (KeyError, TypeError) as e:
        logger.error("Malformed channel metadata: %s", e)
        return

    if not latest:
        logger.info("Version check skipped (latest unresolved). current=%r", current)
        return

    try:
        is_outdated = Version(current) < Version(latest)
    except InvalidVersion as e:
        logger.error(
            "Invalid version while comparing: current=%r, latest=%r (%s)",
            current,
            latest,
            e,
        )
        return

    _update_info(is_outdated, current, latest)
