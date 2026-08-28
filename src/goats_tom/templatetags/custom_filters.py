__all__ = ["starts_with"]
# Standard library imports.

# Related third party imports.
from django import template

# Local application/library specific imports.

register = template.Library()


@register.filter(name="starts_with")
def starts_with(text: str, look_for: str) -> bool:
    """Checks to see if string starts with provided text.

    Parameters
    ----------
    text : `str`
        The text to analyze.
    starts : `str`
        The string to look for at the beginning of the text.

    Returns
    -------
    `bool`
        `True` if text starts with string, `False` if not.

    """
    if isinstance(text, str):
        return text.startswith(look_for)

    return False


@register.simple_tag
def show_shutdown_button() -> bool:
    """Whether the navbar should offer a button that shuts GOATS down.

    Returns
    -------
    bool
        `True` for a desktop install, `False` when `GOATS_SHOW_SHUTDOWN` is
        turned off -- which `environments/server.py` does.

    Notes
    -----
    A tag rather than a context processor, deliberately. A context processor
    has to be listed in ``TEMPLATES``, and an install that upgrades without
    regenerating its settings would not have it -- leaving the variable
    undefined, which a template reads as false, silently removing the button
    from a desktop install that should keep it. Reading the setting here
    needs no registration and defaults to `True`, so the only way to lose the
    button is to ask for that.

    On a shared server the button would let any one of hundreds of PIs stop
    everyone else's ingestion, and the process is supervised by systemd
    rather than by a browser tab.
    """
    from django.conf import settings  # noqa: PLC0415

    return bool(getattr(settings, "GOATS_SHOW_SHUTDOWN", True))
