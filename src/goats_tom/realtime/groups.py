"""Channel-layer group names shared between senders and consumers.

Both `goats_tom.consumers.UpdatesConsumer` (which subscribes) and
`goats_tom.realtime.NotificationInstance` (which publishes) have to agree on
these strings exactly. A mismatch produces no error anywhere -- the message
is delivered to a group nobody is listening on and silently vanishes -- so
they are defined once here rather than written out at each end.
"""

__all__ = ["BROADCAST_GROUP", "user_group_name"]

# The original, all-connected-clients group. Every browser joins it, so
# anything sent here reaches every signed-in user. Kept as the default
# destination so existing notifications behave exactly as before.
BROADCAST_GROUP = "updates_group"


def user_group_name(user) -> str | None:
    """Return the private channel group for one user.

    Parameters
    ----------
    user : `django.contrib.auth.models.User` or None
        The user whose group name to build. Anonymous or `None` users have
        no private group.

    Returns
    -------
    str or None
        ``"user_<pk>"``, or `None` if there is no authenticated user to
        address. Callers treat `None` as "don't send", rather than falling
        back to `BROADCAST_GROUP` -- a message meant for one person should be
        dropped rather than shown to everyone if its recipient can't be
        resolved.

    Notes
    -----
    Keyed on primary key rather than username so the name stays stable if a
    username changes mid-session, and so it can't contain characters the
    channel layer rejects (group names are restricted to alphanumerics,
    hyphens, underscores and periods).
    """
    if user is None:
        return None
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "pk", None) is None:
        return None
    return f"user_{user.pk}"
