"""Expose GOATS_VERSION to all templates."""

__all__ = ["goats_version_processor"]

from functools import lru_cache
from importlib.metadata import version

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


def goats_version_processor(request: HttpRequest) -> dict[str, str]:
    """Inject GOATS version into templates.

    Parameters
    ----------
    request : HttpRequest
        Django request object (unused).

    Returns
    -------
    dict
        Mapping with the key ``"GOATS_VERSION"`` set to the installed version.
    """
    return {"GOATS_VERSION": get_goats_version()}
