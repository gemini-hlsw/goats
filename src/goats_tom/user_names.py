"""How GOATS names one user to another."""

__all__ = ["display_name", "full_name"]


def display_name(user) -> str:
    """Names a person the way GOATS shows them to another user.

    Parameters
    ----------
    user : `django.contrib.auth.models.User` or `None`
        The person to name. `None` is accepted because a stored record can
        outlive the account that made it.

    Returns
    -------
    `str`
        Their full name, failing that their email address, failing that an em
        dash.

    Notes
    -----
    Never the username: it is half of a login credential and names nobody to
    a colleague. The email address is the fallback rather than the first
    choice because a real name is what a colleague recognises -- but an unset
    name is common enough that without a fallback the dash would be most of
    the column.
    """
    if user is None:
        return "—"
    full = (user.get_full_name() or "").strip()
    return full or (user.email or "").strip() or "—"


def full_name(user) -> str:
    """Names a person by their first and last name only.

    Parameters
    ----------
    user : `django.contrib.auth.models.User` or `None`
        The person to name.

    Returns
    -------
    `str`
        Their full name, failing that an em dash. Never the username or email,
        for people shown to every user, such as a TNS group owner.
    """
    if user is None:
        return "—"
    return (user.get_full_name() or "").strip() or "—"
