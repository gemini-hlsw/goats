"""Expose GOATS_VERSION_INFO to all templates."""

__all__ = ["goats_version_info_processor"]

from functools import lru_cache
from importlib.metadata import version
from typing import Any

from django.core.cache import caches
from django.http import HttpRequest


@lru_cache(maxsize=1)
def get_goats_version() -> str:
    """Return the GOATS version (cached).

    Returns
    -------
    str
        Version string obtained from
        ``importlib.metadata.version("goats")``.
    """
    return version("goats")


def goats_version_info_processor(request: HttpRequest) -> dict[str, Any]:
    """Inject GOATS version info into templates.

    Parameters
    ----------
    request : HttpRequest
        Django request object (unused).

    Returns
    -------
    dict[str, Any]
        Mapping with:
        - ``"IS_OUTDATED"`` : bool
            Whether the installed GOATS is older than the latest available.
        - ``"GOATS_VERSION"`` : str
            Currently installed GOATS version.
        - ``"GOATS_LATEST_VERSION"`` : str
            Latest available GOATS version (empty string if unknown).

    """
    cache = caches["redis"]
    version_info = cache.get("version:info") or {}
    current = version_info.get("current", get_goats_version())
    latest = version_info.get("latest", "")
    is_outdated = version_info.get("is_outdated", False)

    return {
        "IS_OUTDATED": is_outdated,
        "GOATS_VERSION": current,
        "GOATS_LATEST_VERSION": latest,
    }
