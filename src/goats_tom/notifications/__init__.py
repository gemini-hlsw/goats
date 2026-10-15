"""Persistent, per-user notifications delivered in-app and by email."""

from .kinds import style
from .service import (
    mark_all_read,
    mark_read,
    notify,
    resolve,
    serialize,
    unread_count,
)

__all__ = [
    "mark_all_read",
    "mark_read",
    "notify",
    "resolve",
    "serialize",
    "style",
    "unread_count",
]
