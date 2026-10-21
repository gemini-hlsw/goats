"""Template tags for GPP."""

from django import template

from goats_tom.utils import get_explore_url

register = template.Library()


@register.simple_tag
def explore_url() -> str:
    """
    Return the base URL of the Explore site for the GPP environment in use.

    Returns
    -------
    str
        The Explore URL, without a trailing slash.
    """
    return get_explore_url()
