__all__ = ["antares_locus_dashboard", "antares_locus_table"]

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from goats_tom.models import AntaresLocus

PAGE_SIZE = 50

DEFAULT_SORT = "-first_seen"

# Maps the `sort` query param value to the actual model field to order by.
# Whitelisted deliberately -- never pass request.GET values straight into
# order_by(), since that would let a request try to sort on arbitrary/
# nonexistent fields.
SORTABLE_FIELDS = {
    "latest_alert": "latest_alert_mjd",
    "first_seen": "first_seen",
    "alert_count": "alert_count",
    "magnitude": "latest_alert_magnitude",
    "in_tns": "in_tns",
}


def _resolve_sort(sort_param: str | None) -> tuple[str, str]:
    """Resolve a `sort` query param into a safe order_by field and its key.

    Parameters
    ----------
    sort_param : str or None
        Raw `sort` query param, e.g. ``"first_seen"`` or ``"-first_seen"``
        (a leading ``-`` means descending). Anything not in
        `SORTABLE_FIELDS` falls back to `DEFAULT_SORT`.

    Returns
    -------
    tuple[str, str]
        ``(order_by_expression, sort_param_used)`` -- the safe Django
        `order_by()` argument, and the normalized `sort` value that was
        actually applied (echoed back so the template can build column
        links and highlight the active sort).

    """
    if not sort_param:
        return DEFAULT_SORT, DEFAULT_SORT

    descending = sort_param.startswith("-")
    key = sort_param.lstrip("-")

    field = SORTABLE_FIELDS.get(key)
    if field is None:
        return DEFAULT_SORT, DEFAULT_SORT

    order_by = f"-{field}" if descending else field
    return order_by, sort_param


def _get_page(request: HttpRequest):
    """Build the paginated, sorted `AntaresLocus` page for this request.

    Parameters
    ----------
    request : `HttpRequest`
        Reads the `page` and `sort` query params.

    Returns
    -------
    tuple
        ``(page, sort_param)`` where `page` is a Django `Page` object and
        `sort_param` is the normalized sort value in effect (for building
        column-header links in the template).

    """
    order_by, sort_param = _resolve_sort(request.GET.get("sort"))
    queryset = AntaresLocus.objects.order_by(order_by)
    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))
    return page, sort_param


@login_required
def antares_locus_dashboard(request: HttpRequest) -> HttpResponse:
    """Render the ANTARES alert/locus browse page.

    Renders the first page directly so the table has real content on first
    paint; the embedded table partial (see `antares_locus_table`) then
    handles paging/sorting via htmx from there.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered dashboard page.

    """
    page, sort_param = _get_page(request)
    return render(
        request,
        "antares_locus_dashboard.html",
        {"page": page, "sort": sort_param},
    )


@login_required
def antares_locus_table(request: HttpRequest) -> HttpResponse:
    """Render one page of the `<table>` of `AntaresLocus` rows.

    Called by htmx when paging, clicking a sortable column header, or on
    the table's own auto-refresh interval (every 15 seconds). In all
    cases the response reflects the same page/sort the request asked for,
    so a row's position only changes when the person explicitly changes
    the sort -- never as a side effect of the periodic refresh.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads the `page` and `sort` query
        parameters.

    Returns
    -------
    `HttpResponse`
        The rendered table partial for the requested page and sort order.

    """
    page, sort_param = _get_page(request)
    return render(
        request,
        "partials/antares_locus_table.html",
        {"page": page, "sort": sort_param},
    )
