"""Template tags for the unified pending-request badge.

Thin wrappers over `goats_tom.pending_requests`. Template tags rather than a
context processor, so the queries run only where the navbar renders them
instead of on every page in the site -- matching how
`goats_tom.templatetags.registration_extras` already did it for account
requests alone.
"""

__all__ = ["pending_requests_tag", "pending_request_total_tag"]

from django import template

from goats_tom import pending_requests as _pending

register = template.Library()


@register.simple_tag(name="pending_requests")
def pending_requests_tag(user):
    """Everything waiting on `user`, one entry per approval flow.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    list of `goats_tom.pending_requests.PendingRequests`
        Only flows with something pending.
    """
    return _pending.pending_requests(user)


@register.simple_tag(name="pending_request_total")
def pending_request_total_tag(user) -> int:
    """Total pending items across all flows, for the username badge.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    int
        Zero when nothing is pending, which the navbar uses to hide the
        badge entirely.
    """
    return _pending.pending_request_total(user)
