"""Template filters for displaying ANTARES locus coordinates and timestamps."""

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def is_active_handler_code(value) -> bool:
    """Whether `value` (a subscription's `handler_code`) represents an
    actually-active filter, not just non-empty text.

    Parameters
    ----------
    value : str or None
        The handler code to check.

    Returns
    -------
    bool
        `False` if `value` is empty or effectively blank (whitespace
        and/or comments only, e.g. a fully commented-out handler --
        see `goats_tom.antares_locus_handler.is_effectively_blank`).
        `True` otherwise.

    Notes
    -----
    A separate filter from just checking `{% if current.handler_code %}`
    in the template, since a fully commented-out handler is non-empty
    text but functionally "no filter" (see
    `goats_tom.antares_locus_handler.is_effectively_blank`) -- this
    filter reflects the actual running behavior, not just field
    presence.
    """
    if not value:
        return False

    from goats_tom.antares_locus_handler import is_effectively_blank  # noqa: PLC0415

    return not is_effectively_blank(value)


@register.filter
def wrap_after_colon(value) -> str:
    """Insert a zero-width space after every ``:`` so long colon-delimited
    strings (e.g. alert IDs like ``ztf_candidate:3477295020415015022``)
    wrap onto a new line at the colon rather than overflowing or breaking
    at an arbitrary character.

    Parameters
    ----------
    value : str or None
        The raw string to insert break opportunities into.

    Returns
    -------
    str
        HTML-escaped value with a zero-width space (``&#8203;``) inserted
        after each colon, marked safe for template rendering. Escaping
        happens first since `value` may come from an external source
        (the ANTARES stream), not trusted application content.

    """
    if not value:
        return mark_safe("&mdash;")

    return mark_safe(escape(str(value)).replace(":", ":&#8203;"))


@register.filter
def mjd_to_utc(mjd) -> str:
    """Convert a Modified Julian Date to a UTC timestamp string.

    Parameters
    ----------
    mjd : float or None
        Modified Julian Date.

    Returns
    -------
    str
        ISO-formatted UTC timestamp (e.g. ``"2026-07-09 03:14:07"``), or an
        em dash if `mjd` is `None` or cannot be parsed.

    """
    if mjd is None:
        return mark_safe("&mdash;")

    from astropy.time import Time  # noqa: PLC0415

    try:
        return Time(float(mjd), format="mjd").utc.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return mark_safe("&mdash;")


@register.filter
def deg_to_ra_sexagesimal(ra_deg) -> str:
    """Convert right ascension in degrees to sexagesimal (HH:MM:SS.ss).

    Parameters
    ----------
    ra_deg : float or None
        Right ascension in degrees.

    Returns
    -------
    str
        Sexagesimal RA string, or an em dash if `ra_deg` is `None` or
        cannot be parsed.

    """
    if ra_deg is None:
        return mark_safe("&mdash;")

    from astropy.coordinates import Angle  # noqa: PLC0415
    from astropy import units as u  # noqa: PLC0415

    try:
        angle = Angle(float(ra_deg), unit=u.degree)
        return angle.to_string(unit=u.hourangle, sep=":", precision=2, pad=True)
    except (ValueError, TypeError):
        return mark_safe("&mdash;")


@register.filter
def deg_to_dec_sexagesimal(dec_deg) -> str:
    """Convert declination in degrees to sexagesimal (+/-DD:MM:SS.ss).

    Parameters
    ----------
    dec_deg : float or None
        Declination in degrees.

    Returns
    -------
    str
        Sexagesimal Dec string, or an em dash if `dec_deg` is `None` or
        cannot be parsed.

    """
    if dec_deg is None:
        return mark_safe("&mdash;")

    from astropy.coordinates import Angle  # noqa: PLC0415
    from astropy import units as u  # noqa: PLC0415

    try:
        angle = Angle(float(dec_deg), unit=u.degree)
        return angle.to_string(
            unit=u.degree, sep=":", precision=2, alwayssign=True, pad=True
        )
    except (ValueError, TypeError):
        return mark_safe("&mdash;")
