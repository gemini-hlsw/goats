"""Expose the Gemini Explore URL for the active GPP environment to templates."""

__all__ = ["gpp_explore_processor"]

from django.conf import settings
from django.http import HttpRequest


def gpp_explore_processor(request: HttpRequest) -> dict:
    """Make the Explore base URL available to every template.

    Parameters
    ----------
    request : `HttpRequest`
        The current request. Unused; required by the context-processor
        interface.

    Returns
    -------
    dict
        ``{"gpp_explore_url": ...}``.

    Notes
    -----
    Exists so the navbar link can follow `GPP_ENV` rather than hardcoding
    production. A template cannot read `django.conf.settings` directly, and
    adding the value to every view that renders the navbar would mean it was
    right in most places and wrong wherever somebody forgot.

    The value itself is derived from `GPP_ENV` in the settings package, so a
    deployment pointed at the development ODB links to development Explore --
    the two cannot be configured into disagreeing.
    """
    return {
        "gpp_explore_url": getattr(
            settings, "GPP_EXPLORE_URL", "https://explore.gemini.edu"
        )
    }
