"""Wrappers around `tom_tns`'s report and classify tags.

`tom_tns.templatetags.tns_extras` imports ``default_authors()`` by name at
module load, so the patch `goats_tom.apps` applies never reaches it.
Rebinding the name in ``AppConfig.ready()`` would mean importing that module
at startup, where it calls ``get_tns_values()`` four times at module scope --
four network requests in front of every process start. So the tags are
wrapped instead: upstream builds the form as always and this only overwrites
the author field afterwards.
"""

__all__ = ["report_to_tns", "classify_with_tns"]

from django import template
from django.conf import settings

from goats_tom.middleware.tns import current_tns_creds

register = template.Library()


def _recommended_authors() -> str:
    """Return the author list for the group being posted through.

    Returns
    -------
    str
        The owner's recommended co-authors, or ``""`` when there are none.
        Read from the credential payload, so the middleware alone decides
        which group is in play and this cannot disagree with it.
    """
    creds = current_tns_creds.get()
    if not creds:
        return ""
    return (creds.get("recommended_authors") or "").strip()


def _drop_null_choices(form) -> None:
    """Remove unresolvable entries from the two TNS-populated dropdowns.

    Parameters
    ----------
    form : `django.forms.Form`
        The report or classify form.

    Notes
    -----
    `tom_tns.forms.TNSReportForm.__init__` appends the lookup for ``"None"``
    without checking it resolved, so when TNS's cached values are empty
    `choices` becomes ``[None]`` and `Select.optgroups` raises `TypeError`
    unpacking it -- a 500 on any instance that cannot reach TNS. Dropping
    the nulls leaves an empty dropdown and still renders the photometry the
    astronomer came to check.
    """
    for name in ("reporting_group", "discovery_data_source"):
        field = form.fields.get(name)
        if field is None:
            continue
        field.choices = [
            choice for choice in (field.choices or []) if choice is not None
        ]


def _submitter_credit(user) -> str:
    """Return the author line for a group that recommends none.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        Whoever is filling the form in.

    Returns
    -------
    str
        ``"<their name>, using <TOM_NAME>"``, or ``""`` if they have set no
        name.

    Notes
    -----
    What upstream means to produce. `tom_tns.templatetags.tns_extras` asks
    for ``getattr(user, "get_full_name()", "Anonymous User")`` -- an
    attribute name with the call parentheses inside the string, which no
    object has -- so every report it pre-fills is credited to "Anonymous
    User" whatever the account is called.

    No email fallback, unlike `custom_filters.display_name`: this text goes
    on a public record, where an address is not a byline.
    """
    full_name = (user.get_full_name() or "").strip() if user is not None else ""
    if not full_name:
        return ""
    return f"{full_name}, using {settings.TOM_NAME}"


def _with_authors(result: dict, field: str, user=None) -> dict:
    """Overwrite one field's initial value with the recommended authors.

    Parameters
    ----------
    result : dict
        The context returned by the upstream inclusion tag.
    field : str
        ``"reporter"`` or ``"classifier"``, the two names `tom_tns` uses for
        an author list.
    user : `django.contrib.auth.models.User`, optional
        Whoever is filling the form in, credited when the group recommends
        no authors of its own.

    Returns
    -------
    dict
        The same context, mutated.

    Notes
    -----
    Mutating `form.initial` after construction works because an unbound
    field reads it at render time, not in ``__init__``.

    The fallback is carried on the widget as ``data-default-authors`` so the
    page can put it back when the reader switches to a group that recommends
    none. Without it the script blanked the field, which differed from what
    the same case showed on first render.
    """
    form = result.get("form")
    if form is None:
        return result

    _drop_null_choices(form)

    if field not in form.fields:
        return result

    fallback = _submitter_credit(user)
    form.fields[field].widget.attrs["data-default-authors"] = fallback

    authors = _recommended_authors()
    form.initial[field] = authors or fallback or form.initial.get(field, "")
    return result


@register.inclusion_tag("tom_tns/partials/tns_report_form.html", takes_context=True)
def report_to_tns(context):
    """Render the AT report form, pre-filling recommended co-authors.

    Parameters
    ----------
    context : `django.template.Context`
        The template context, which must contain ``target`` and ``request``.

    Returns
    -------
    dict
        The inclusion-tag context.
    """
    from tom_tns.templatetags.tns_extras import (  # noqa: PLC0415
        report_to_tns as upstream_report_to_tns,
    )

    return _with_authors(
        upstream_report_to_tns(context), "reporter", context["request"].user
    )


@register.inclusion_tag("tom_tns/partials/tns_classify_form.html", takes_context=True)
def classify_with_tns(context):
    """Render the classification form, pre-filling recommended co-authors.

    Parameters
    ----------
    context : `django.template.Context`
        The template context, which must contain ``target`` and ``request``.

    Returns
    -------
    dict
        The inclusion-tag context.
    """
    from tom_tns.templatetags.tns_extras import (  # noqa: PLC0415
        classify_with_tns as upstream_classify_with_tns,
    )

    return _with_authors(
        upstream_classify_with_tns(context), "classifier", context["request"].user
    )
