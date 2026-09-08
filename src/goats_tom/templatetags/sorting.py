from typing import Any

from django import template

register = template.Library()


@register.inclusion_tag("partials/sortable_header.html", takes_context=True)
def sortable_header(
    context: template.Context, field: str, label: str
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
    """
    # Inclusion tags render in a fresh context, so `request` may only be
    # reachable as an attribute of the parent `RequestContext`.
    request = context.get("request") or getattr(context, "request", None)
    params = request.GET.copy()
    current = params.get("order", "")
    descending = current == f"-{field}"
    ascending = current == field
    # Default to newest first, then toggle.
    params["order"] = field if descending else f"-{field}"
    # A new ordering invalidates the current page number.
    params.pop("page", None)
    return {
        "label": label,
        "url": f"?{params.urlencode()}",
        "ascending": ascending,
        "descending": descending,
    }
