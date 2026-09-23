"""
Channel-layer group names, shared by the senders and the consumers.

Both ends have to agree on these strings exactly. A mismatch raises nothing
anywhere -- the message goes to a group nobody listens on and vanishes -- so
they are defined once here instead of being written out at each end.
"""

__all__ = ["BROADCAST_GROUP", "DRAGONS_PREFIX", "UPDATES_PREFIX", "user_group"]

BROADCAST_GROUP = "updates_group"
"""The group every client joins, for announcements meant for everyone."""

UPDATES_PREFIX = "updates_user"
"""Prefix of the notification and download group of one user."""

DRAGONS_PREFIX = "dragons_user"
"""Prefix of the DRAGONS reduction group of one user."""


def user_group(prefix: str, user_id: int | None) -> str | None:
    """The private group one user listens on.

    Parameters
    ----------
    prefix : `str`
        The kind of update the group carries, e.g. `UPDATES_PREFIX`.
    user_id : `int | None`
        The user to address.

    Returns
    -------
    `str | None`
        ``"<prefix>_<user_id>"``, or `None` when there is no user to address.
        Callers drop the message rather than falling back to `BROADCAST_GROUP`:
        a message meant for one person should be lost rather than shown to
        everyone.

    Notes
    -----
    Keyed on the primary key so the name survives a username change, and so it
    cannot contain characters the channel layer rejects.
    """
    if user_id is None:
        return None
    return f"{prefix}_{user_id}"
