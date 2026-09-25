"""Template tags for the credentials a user has stored."""

from typing import Any

from django import template
from django.contrib.auth.models import User

from goats_tom.credentials import get_credential_status

register = template.Library()


@register.simple_tag(takes_context=True)
def credential_services(context: dict[str, Any], user: User) -> list[dict[str, Any]]:
    """Return every credential service with whether `user` has one stored.

    Parameters
    ----------
    context : `dict[str, Any]`
        The template context, read for the URL being served.
    user : `User`
        Whose stored credentials to report on.

    Returns
    -------
    `list[dict[str, Any]]`
        One entry per service, with its `label`, `url_name`, `stored` flag and
        whether it `is_current`.
    """
    match = getattr(context.get("request"), "resolver_match", None)
    return get_credential_status(user, getattr(match, "url_name", None))
