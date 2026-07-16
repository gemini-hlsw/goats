__all__ = [
    "antares_locus_dashboard",
    "antares_locus_table",
    "antares_locus_save_targets",
    "antares_locus_saved_status",
]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from tom_targets.models import Target

from goats_tom.antares_target_save import (
    SaveLocusError,
    locus_is_saved_as_target,
    save_locus_as_target,
)
from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

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


def _saved_locus_ids(locus_ids: list[str]) -> set[str]:
    """Batch-check which of the given locus IDs are already saved targets.

    Two queries total regardless of how many locus IDs are given, rather
    than `locus_is_saved_as_target()` (2 queries each) called per ID --
    used by both the main table render (polled every 15s) and the fast
    saved-status poll (`antares_locus_saved_status`, polled every ~3s),
    so both stay cheap under frequent polling.

    Parameters
    ----------
    locus_ids : list of str
        Locus IDs to check.

    Returns
    -------
    set of str
        The subset of `locus_ids` that are saved, as either a `Target`
        name or a `TargetName` alias.
    """
    saved_by_name = set(
        Target.objects.filter(name__in=locus_ids).values_list("name", flat=True)
    )
    saved_by_alias = set(
        Target.objects.filter(aliases__name__in=locus_ids).values_list(
            "aliases__name", flat=True
        )
    )
    return saved_by_name | saved_by_alias


def _get_page(request: HttpRequest):
    """Build the paginated, sorted `AntaresLocus` page for this request,
    annotating each row with whether it's already saved as a `Target`.

    Parameters
    ----------
    request : `HttpRequest`
        Reads the `page` and `sort` query params.

    Returns
    -------
    tuple
        ``(page, sort_param)`` where `page` is a Django `Page` object
        (each locus on it additionally has a `.is_saved_target` attribute
        set) and `sort_param` is the normalized sort value in effect (for
        building column-header links in the template).

    """
    order_by, sort_param = _resolve_sort(request.GET.get("sort"))
    queryset = AntaresLocus.objects.order_by(order_by)
    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))

    page_locus_ids = [locus.locus_id for locus in page]
    saved_locus_ids = _saved_locus_ids(page_locus_ids)
    for locus in page:
        locus.is_saved_target = locus.locus_id in saved_locus_ids

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


@login_required
@require_POST
def antares_locus_save_targets(request: HttpRequest) -> HttpResponse:
    """Save one or more selected loci as GOATS `Target`s.

    Called by the dashboard's "Save selected" button. Reads
    `locus_id` from `request.POST` (a checkbox's `getlist`, since
    multiple rows can be selected), saves each one not already saved
    (via `goats_tom.antares_target_save`), and reports a summary via
    Django messages before redirecting back to the dashboard.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads the `locus_id` POST field
        (repeated for each selected row) and, to preserve the user's
        current view, the `page` and `sort` POST fields.

    Returns
    -------
    `HttpResponse`
        Redirect back to the dashboard, preserving `page`/`sort` if given.

    """
    locus_ids = request.POST.getlist("locus_id")

    if not locus_ids:
        messages.warning(request, "No loci selected to save.")
    else:
        saved, skipped, failed = 0, 0, 0
        for locus_id in locus_ids:
            if locus_is_saved_as_target(locus_id):
                skipped += 1
                continue
            try:
                save_locus_as_target(locus_id)
                saved += 1
            except SaveLocusError:
                logger.exception("Failed to save locus_id=%s as a target.", locus_id)
                failed += 1

        if saved:
            messages.success(request, f"Saved {saved} locus/loci as targets.")
        if skipped:
            messages.info(
                request, f"{skipped} selected locus/loci were already saved."
            )
        if failed:
            messages.error(
                request,
                f"Failed to save {failed} locus/loci as targets; see logs "
                f"for details.",
            )

    redirect_url = reverse("antares-locus-dashboard")
    page = request.POST.get("page")
    sort = request.POST.get("sort")
    query = []
    if page:
        query.append(f"page={page}")
    if sort:
        query.append(f"sort={sort}")
    if query:
        redirect_url = f"{redirect_url}?{'&'.join(query)}"
    return redirect(redirect_url)


@login_required
def antares_locus_saved_status(request: HttpRequest) -> JsonResponse:
    """Return which of the given locus IDs are currently saved as targets.

    A small, fast endpoint (JSON, not a page/partial render) so the
    dashboard can poll it frequently (every few seconds) to pick up saves
    made elsewhere -- most notably the antares2goats browser extension,
    which saves targets directly from the ANTARES portal, in a different
    browser tab the dashboard has no other way of knowing about. This is
    deliberately not full push/WebSocket-based updates; a fast poll of a
    cheap, batched, two-query endpoint was chosen instead to keep the
    implementation simple for a "noticeably faster than the 15s table
    refresh, but not real-time" requirement.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads the `locus_id` query parameter,
        repeated for each locus ID currently rendered in the dashboard
        (e.g. ``?locus_id=A&locus_id=B``).

    Returns
    -------
    `JsonResponse`
        ``{"saved": [locus_id, ...]}`` -- the subset of the requested
        locus IDs that are currently saved as targets.

    """
    locus_ids = request.GET.getlist("locus_id")
    saved = _saved_locus_ids(locus_ids) if locus_ids else set()
    return JsonResponse({"saved": sorted(saved)})
