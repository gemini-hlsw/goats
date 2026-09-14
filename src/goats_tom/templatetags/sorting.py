from typing import Any

from django import template

register = template.Library()


@register.inclusion_tag("partials/sortable_header.html", takes_context=True)
def sortable_header(
    context: template.Context,
    field: str,
    label: str,
    suffix: str = "",
    css_class: str = "",
) -> dict[str, Any]:
    """
    Render a table header that toggles ``?order=`` between ascending and
    descending on `field`, keeping the other query parameters intact.

    Parameters
    ----------
    context : `template.Context`
        Template context, used to read the current request.
    field : `str`
        Model field to order by; must be allowed by the view's
        ``orderable_fields``.
    label : `str`
        Header text.
    suffix : `str`, optional
        Suffix for the query parameters, so a secondary table on the same page
        can sort independently (e.g. ``"_saved"`` uses ``order_saved`` and
        resets ``page_saved``).
    css_class : `str`, optional
        Classes for the rendered ``<th>``, so the header keeps the styling the
        surrounding table gives its own columns.
    """
    # Inclusion tags render in a fresh context, so `request` may only be
    # reachable as an attribute of the parent `RequestContext`.
    request = context.get("request") or getattr(context, "request", None)
    params = request.GET.copy()
    order_param = f"order{suffix}"
    current = context.get(f"current_order{suffix}", params.get(order_param, ""))
    descending = current == f"-{field}"
    ascending = current == field
    # Default to newest first, then toggle.
    params[order_param] = field if descending else f"-{field}"
    # A new ordering invalidates the current page number.
    params.pop(f"page{suffix}", None)
    params.pop("ordering", None)
    return {
        "label": label,
        "url": f"?{params.urlencode()}",
        "ascending": ascending,
        "descending": descending,
        "css_class": css_class,
    }
