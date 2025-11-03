"""
Expose version info to all templates under the 'version_info' namespace.
"""

__all__ = ["goats_version_info_processor"]

import logging
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from django.core.cache import caches
from django.http import HttpRequest

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_goats_version() -> str:
    """Return the currently installed GOATS version (cached).

    Returns
    -------
    str
        Version string obtained from ``importlib.metadata.version("goats")``.
        Returns ``"unknown"`` if the package is not installed.
    """
    try:
        return version("goats")
    except PackageNotFoundError:
        logger.warning("GOATS package not found when retrieving version.")
        return "unknown"


def goats_version_info_processor(request: HttpRequest) -> dict[str, Any]:
    """Inject version info into the template context under the `version_info` key.

    Parameters
    ----------
    request : HttpRequest
        Django request object (unused).

    Returns
    -------
    dict[str, Any]
        Dictionary with `version_info` key containing current/latest version
        info from the Redis cache.
    """
    cache = caches["redis"]
    version_info = cache.get("version_info") or {}

    # Fallback to current version if not in cache.
    # This can happen if the version check task has not run yet.
    current_version = version_info.get("current") or get_goats_version()
    latest_version = version_info.get("latest", "")
    is_outdated = version_info.get("is_outdated", False)
    # Fallback to '/latest/' docs if 'current_version' is not known.
    version_for_docs = (
        current_version
        if current_version and current_version != "unknown"
        else "latest"
    )
    doc_url = f"https://goats.readthedocs.io/en/{version_for_docs}/index.html"
    return {
        "version_info": {
            "current": current_version,
            "latest": latest_version,
            "is_outdated": is_outdated,
            "doc_url": doc_url,
        }
    }
