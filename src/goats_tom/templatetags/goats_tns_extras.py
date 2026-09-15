"""Wrappers around `tom_tns`'s report and classify tags.

`tom_tns.templatetags.tns_extras` seeds the author field from
``default_authors()``, which it imports *by name* at module load. That
binding is fixed at import time, so the patch `goats_tom.apps` applies to
`tom_tns.tns_api.default_authors` never reaches it.

The obvious fix -- rebinding the name on `tns_extras` during
``AppConfig.ready()`` -- would mean importing that module at startup, and it
calls ``get_tns_values()`` four times at module scope. That would put four
network requests in front of every process start, including migrations and
management commands, to fix a value only ever needed while rendering a page.

So the tags are wrapped here instead. Upstream builds the form exactly as it
always did; this only overwrites the author field afterwards, at the point
where the credentials for *this* request are known. Everything else about
the form -- the photometry and spectroscopy defaults, the file choices, the
layout -- is upstream's and stays untouched, so this does not have to be
kept in step with it.
"""

__all__ = ["report_to_tns", "classify_with_tns"]

from django import template

from goats_tom.middleware.tns import current_tns_creds

register = template.Library()


def _recommended_authors() -> str:
    """Return the author list for the group being posted through.

    Returns
    -------
    str
        The owner's recommended co-authors, or ``""`` when there are none.

    Notes
    -----
    Read from the credential payload rather than the database, so there is
    exactly one place that decides which group is in play -- the middleware,
    via `goats_tom.tns_membership.resolve_posting_option`. Looking the group
    up again here could disagree with what the submission will actually use.
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
    `tom_tns.forms.TNSReportForm.__init__` builds `reporting_group` by
    looking each group name up against TNS's own cached values, and then
    appends the lookup for ``"None"`` *unconditionally* -- without checking
    it resolved. When the values endpoint is unreachable that cache is
    empty, every lookup returns `None`, and `choices` ends up as ``[None]``.
    Django's `Select.optgroups` then unpacks each choice into a
    ``(value, label)`` pair and raises `TypeError`, so the whole page 500s.

    That was unreachable before: `tns_configured` was computed from
    settings GOATS does not populate, so the page always stopped at the
    "credentials not configured" banner and never rendered a form. Fixing
    that (see `goats_tom.views.tns_report.GOATSTNSFormView`) makes this
    path live, which would turn a clear banner into a server error on any
    instance that cannot reach TNS -- a worse failure than the one being
    fixed.

    Dropping the null entries leaves an empty dropdown instead. That is
    honest about the situation and still lets the rest of the form render,
    including the photometry the astronomer came to check.
    """
    for name in ("reporting_group", "discovery_data_source"):
        field = form.fields.get(name)
        if field is None:
            continue
        field.choices = [
            choice
            for choice in (field.choices or [])
            if choice is not None
        ]


def _with_authors(result: dict, field: str) -> dict:
    """Overwrite one field's initial value with the recommended authors.

    Parameters
    ----------
    result : dict
        The context returned by the upstream inclusion tag.
    field : str
        ``"reporter"`` or ``"classifier"`` -- the two names `tom_tns` uses
        for what is the same thing, an author list.

    Returns
    -------
    dict
        The same context, mutated.

    Notes
    -----
    Mutating `form.initial` after construction works because an unbound
    field reads its value through `Form.get_initial_for_field`, which
    consults that dict at render time rather than at ``__init__``. Rebuilding
    the form with different initial data would mean duplicating everything
    upstream does to assemble it.

    Blank is left alone rather than written, so a group with no author list
    keeps `tom_tns`'s own default of the submitting user's name.
    """
    form = result.get("form")
    if form is None:
        return result

    _drop_null_choices(form)

    authors = _recommended_authors()
    if authors and field in form.fields:
        form.initial[field] = authors
    return result


@register.inclusion_tag(
    "tom_tns/partials/tns_report_form.html", takes_context=True
)
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

    return _with_authors(upstream_report_to_tns(context), "reporter")


@register.inclusion_tag(
    "tom_tns/partials/tns_classify_form.html", takes_context=True
)
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

    return _with_authors(upstream_classify_with_tns(context), "classifier")
