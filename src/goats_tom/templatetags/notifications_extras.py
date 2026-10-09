"""Template tags for the notification bell."""

__all__ = ["inbox_summary", "kind_icon", "kind_color", "short_time"]

from datetime import datetime

from django import template
from django.utils import timezone
from django.utils.dateformat import format as format_date

from goats_tom.models import Notification
from goats_tom.notifications import style, unread_count

register = template.Library()

RECENT = 10
"""How many notifications the bell's dropdown lists."""


@register.simple_tag
def inbox_summary(user) -> dict:
    """Unread count and latest notifications for the navbar bell.

    A tag rather than a context processor, so the queries run only where the
    bell renders.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    dict
        ``unread`` (int), ``recent`` (latest `Notification` rows) and
        ``has_unread`` (whether any of those is unread). Empty for anonymous
        users.
    """
    if not getattr(user, "is_authenticated", False):
        return {"unread": 0, "recent": [], "has_unread": False}
    recent = list(Notification.objects.filter(recipient=user)[:RECENT])
    return {
        "unread": unread_count(user),
        "recent": recent,
        "has_unread": any(not notification.is_read for notification in recent),
    }


@register.filter
def kind_icon(kind: str) -> str:
    """Font Awesome icon of a notification kind."""
    return style(kind)[0]


@register.filter
def kind_color(kind: str) -> str:
    """Bootstrap colour of a notification kind."""
    return style(kind)[1]


@register.filter
def short_time(when: datetime | None, now: datetime | None = None) -> str:
    """Compact age of a timestamp, as the bell shows it.

    Parameters
    ----------
    when : datetime | None
        The timestamp.
    now : datetime | None, optional
        Reference time, by default the current one.

    Returns
    -------
    str
        ``"now"``, ``"5m"``, ``"3h"``, ``"2d"``, or the date (``"8 Oct"``, with
        the year when it is not the current one). Mirrors
        ``NotificationInbox.shortTime`` in ``notification_inbox.js``.
    """
    if when is None:
        return ""
    now = now or timezone.now()
    minutes = int((now - when).total_seconds() // 60)
    if minutes < 1:
        return "now"
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 60 * 24:
        return f"{minutes // 60}h"
    if minutes < 60 * 24 * 7:
        return f"{minutes // (60 * 24)}d"
    when = timezone.localtime(when)
    return format_date(when, "j M" if when.year == now.year else "j M Y")
