__all__ = [
    "antares_locus_dashboard",
    "antares_locus_table",
    "antares_locus_save_targets",
    "antares_locus_saved_status",
    "antares_locus_clear",
    "antares_dashboard_status",
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

from goats_tom.antares_access import (
    accessible_subscriptions,
    can_configure,
    can_save_targets,
    get_subscription_for_view,
)
from goats_tom.antares_target_save import (
    SaveLocusError,
    locus_is_saved_as_target,
    save_locus_as_target,
)
from goats_tom.models import (
    AntaresLocus,
    AntaresStreamSubscription,
    AntaresTargetSave,
)

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
    "topic": "latest_alert_topic",
    "magnitude": "latest_alert_magnitude",
}


def _visible_subscription(request: HttpRequest):
    """Return the subscription whose dashboard this request may view.

    Every dashboard query is scoped through this, so loci isolation is
    enforced at the query level rather than by filtering after the fact
    (loci are stored per subscription -- see
    `goats_tom.models.AntaresLocus.subscription`).

    Resolves to the requesting user's own subscription by default, or to
    an explicitly requested one (``?subscription=<pk>``) when they have
    been granted view access to another PI's dashboard. Access is decided
    by `goats_tom.antares_access`, not here, so there is one definition of
    it shared with the save and clear views.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request. Reads the optional `subscription` query param.

    Returns
    -------
    `goats_tom.models.AntaresStreamSubscription` or None
        The subscription to render, or `None` if the user has no dashboard
        of their own and no access to anyone else's -- in which case the
        dashboard renders empty rather than erroring, since that is a
        normal state for a new account.

    Notes
    -----
    A `subscription` param naming a dashboard the user may *not* view
    resolves to `None`, never to a fallback they can see. Silently
    substituting a different dashboard would show data under the wrong
    heading, which is worse than showing nothing.
    """
    raw_id = request.GET.get("subscription") or request.POST.get("subscription")
    subscription_id = None
    if raw_id:
        try:
            subscription_id = int(raw_id)
        except (TypeError, ValueError):
            # A non-numeric value is a malformed request, not a request for
            # the default dashboard -- resolve to nothing rather than
            # quietly showing the user their own.
            return None
    return get_subscription_for_view(request.user, subscription_id)


def _dashboard_context(request: HttpRequest, subscription) -> dict:
    """Build the context every dashboard template needs about access.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    subscription : `goats_tom.models.AntaresStreamSubscription` or None
        The dashboard being shown.

    Returns
    -------
    dict
        `available_dashboards` (every dashboard this user may view, for the
        switcher), `is_owner`, and `may_save`.

    Notes
    -----
    A user can belong to several PI groups, so "the dashboard" is a choice
    rather than a given. The switcher is only worth rendering when there is
    more than one, but the list is always supplied so the template can also
    name the one being shown -- important because two PIs' dashboards look
    identical otherwise.

    `is_owner` drives whether configuration and clearing are offered; members
    get a read-only view (see `goats_tom.antares_access.can_configure`).
    """
    return {
        "available_dashboards": list(
            accessible_subscriptions(request.user).select_related("owner")
        ),
        "is_owner": can_configure(request.user, subscription),
        "may_save": can_save_targets(request.user, subscription),
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
        building column-header links in the template). The page contains
        only loci ingested by the requesting user's own subscription, and
        is empty if they have none.

    """
    order_by, sort_param = _resolve_sort(request.GET.get("sort"))
    subscription = _visible_subscription(request)
    # `none()` rather than an unfiltered queryset when the user has no
    # subscription: showing every user's loci to anyone without one of
    # their own would be exactly the leak this scoping exists to prevent.
    queryset = (
        AntaresLocus.objects.filter(subscription=subscription).order_by(order_by)
        if subscription is not None
        else AntaresLocus.objects.none()
    )
    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", 1))

    page_locus_ids = [locus.locus_id for locus in page]
    saved_locus_ids = _saved_locus_ids(page_locus_ids)

    # Who saved each one. One extra query for the whole page (not per
    # row), matching how `_saved_locus_ids` batches its own lookup.
    # `select_related` avoids a further query per row to resolve the
    # user. Only loci confirmed saved above get attribution shown, so a
    # stale row here (target deleted outside this module) is never
    # displayed -- see `AntaresTargetSave`'s docstring.
    saved_by_locus_id = {
        record.locus_id: record.saved_by
        for record in AntaresTargetSave.objects.filter(
            locus_id__in=page_locus_ids
        ).select_related("saved_by")
    }

    for locus in page:
        locus.is_saved_target = locus.locus_id in saved_locus_ids
        locus.saved_by_user = (
            saved_by_locus_id.get(locus.locus_id)
            if locus.is_saved_target
            else None
        )

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
    current_subscription = _visible_subscription(request)
    return render(
        request,
        "antares_locus_dashboard.html",
        {
            "page": page,
            "sort": sort_param,
            "current_subscription": current_subscription,
            **_dashboard_context(request, current_subscription),
        },
    )


@login_required
def antares_dashboard_status(request: HttpRequest) -> HttpResponse:
    """Render just the dashboard's Kafka subscription status/error banner,
    for htmx polling.

    Mirrors `goats_tom.views.antares_stream_subscribe.antares_stream_status`
    (the ingestion page's equivalent): the actor that starts/stops
    ingestion runs asynchronously in a Dramatiq worker, so a static,
    one-time render of `current_subscription` on page load can miss a
    status change (e.g. a startup failure recorded moments after the page
    was loaded) until some other navigation triggers a fresh render. This
    endpoint is polled every few seconds so the dashboard's banner catches
    up on its own too, not just the ingestion page's.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered status partial.

    """
    current_subscription = _visible_subscription(request)
    return render(
        request,
        "partials/antares_dashboard_status.html",
        {
            "current_subscription": current_subscription,
            **_dashboard_context(request, current_subscription),
        },
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
    subscription = _visible_subscription(request)
    if subscription is None:
        messages.error(request, "You have no ANTARES dashboard to save from.")
        return redirect("antares-locus-dashboard")

    if not can_save_targets(request.user, subscription):
        messages.error(
            request,
            "You do not have permission to save targets from this dashboard.",
        )
        return redirect("antares-locus-dashboard")

    requested_ids = request.POST.getlist("locus_id")

    # Only loci actually present on the dashboard being saved from. The
    # posted IDs are attacker-controlled, and without this check any user
    # who could reach this endpoint could save an arbitrary locus by ID --
    # including ones from another PI's dashboard that they were never shown.
    # Restricting to the subscription's own rows makes the permission check
    # above meaningful rather than advisory.
    locus_ids = list(
        AntaresLocus.objects.filter(
            subscription=subscription, locus_id__in=requested_ids
        ).values_list("locus_id", flat=True)
    )

    rejected = len(set(requested_ids)) - len(set(locus_ids))
    if rejected:
        logger.warning(
            "Ignored %d locus id(s) posted by user %s that are not on "
            "subscription id=%s's dashboard.",
            rejected,
            request.user.username,
            subscription.pk,
        )

    # Share saved targets with the dashboard owner's team, not the saving
    # user's own group -- a student saving from their PI's dashboard is
    # contributing to that PI's programme, so the target belongs to that
    # team. Resolved from the subscription rather than from `request.user`
    # for exactly that reason.
    share_group = None
    owner_pi_group = getattr(subscription.owner, "antares_pi_group", None)
    if owner_pi_group is not None:
        share_group = owner_pi_group.group

    if not locus_ids:
        messages.warning(request, "No loci selected to save.")
    else:
        saved, shared, failed = 0, 0, 0
        for locus_id in locus_ids:
            # An already-saved locus is shared, not skipped. There is one
            # `Target` per locus and it is shared between teams (see
            # `goats_tom.antares_target_save`), so saving one somebody else
            # already saved is how this team gains access to it. The previous
            # behaviour -- reporting "already saved" and doing nothing --
            # would have left them unable to see a target that exists.
            already_saved = locus_is_saved_as_target(locus_id)
            try:
                save_locus_as_target(
                    locus_id,
                    saved_by=request.user,
                    share_with_group=share_group,
                )
            except SaveLocusError:
                logger.exception("Failed to save locus_id=%s as a target.", locus_id)
                failed += 1
                continue

            if already_saved:
                shared += 1
            else:
                saved += 1

        if saved:
            messages.success(request, f"Saved {saved} locus/loci as targets.")
        if shared:
            messages.info(
                request,
                f"{shared} selected locus/loci already existed as targets; "
                f"you now have access to them.",
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
        ``{"saved": [locus_id, ...], "saved_by": {locus_id: username}}``
        -- the subset of the requested locus IDs currently saved as
        targets, plus who saved each one where that's known. Attribution
        is included here (rather than left to the slower full-table
        refresh) so the "Saved By" column updates in step with the
        "Saved" badge instead of lagging behind it.

    """
    subscription = _visible_subscription(request)
    requested_ids = request.GET.getlist("locus_id")
    # Same scoping as the save endpoint: only report on loci that are
    # actually on the dashboard this user may view, so this can't be used to
    # probe whether an arbitrary locus ID has been saved by someone else.
    locus_ids = (
        list(
            AntaresLocus.objects.filter(
                subscription=subscription, locus_id__in=requested_ids
            ).values_list("locus_id", flat=True)
        )
        if subscription is not None and requested_ids
        else []
    )
    saved = _saved_locus_ids(locus_ids) if locus_ids else set()

    saved_by = {}
    if saved:
        for record in AntaresTargetSave.objects.filter(
            locus_id__in=saved
        ).select_related("saved_by"):
            if record.saved_by is not None:
                saved_by[record.locus_id] = record.saved_by.username

    return JsonResponse({"saved": sorted(saved), "saved_by": saved_by})


@login_required
@require_POST
def antares_locus_clear(request: HttpRequest) -> HttpResponse:
    """Delete all `AntaresLocus` rows, clearing the dashboard manually.

    Clears only the requesting user's own dashboard, never anyone
    else's.

    This is independent of the 1-day auto-cleanup
    (`goats_tom.tasks.cleanup_stale_antares_loci`) and of the Kafka
    consumer itself -- deleting these staging rows does not stop
    ingestion, and does not touch any GOATS `Target`s already saved from
    loci in this table. New loci will simply start repopulating the table
    again as the stream continues (or resume with the next locus update,
    if ingestion is currently stopped).

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        Redirect back to the dashboard.

    """
    subscription = _visible_subscription(request)
    if subscription is None:
        messages.info(request, "You have no ANTARES dashboard to clear.")
        return redirect("antares-locus-dashboard")

    # Owner-only, deliberately not delegable to members or superusers --
    # clearing destroys the whole team's view of the stream. See
    # `goats_tom.antares_access.can_configure`.
    if not can_configure(request.user, subscription):
        messages.error(
            request, "Only the dashboard's owner can clear it."
        )
        return redirect("antares-locus-dashboard")

    # Scoped to this user's own subscription. Previously this deleted every
    # row in the table, which with per-user dashboards would let any
    # logged-in user wipe everyone else's.
    deleted_count, _ = AntaresLocus.objects.filter(
        subscription=subscription
    ).delete()
    logger.info(
        "Manually cleared %d ANTARES locus rows from %s's dashboard.",
        deleted_count,
        request.user.username,
    )
    messages.success(request, f"Cleared {deleted_count} loci from the dashboard.")
    return redirect("antares-locus-dashboard")
