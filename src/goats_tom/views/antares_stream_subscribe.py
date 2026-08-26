__all__ = [
    "antares_stream_subscribe",
    "antares_stream_status",
    "antares_available_topics",
]

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from goats_tom.antares_access import (
    accessible_subscriptions,
    get_subscription_for_view,
)
from goats_tom.antares_stream_control import (
    TopicListError,
    fetch_available_topics,
    restart_antares_stream,
    stop_antares_stream,
)
from goats_tom.forms import AntaresStreamSubscribeForm
from goats_tom.models import AntaresStreamSubscription
from goats_tom.models.antares_stream_subscription import DEFAULT_MAX_TRIGGERS

logger = logging.getLogger(__name__)


def _apply_template_initial(initial: dict, current) -> None:
    """Seed the hidden template fields from a saved subscription.

    Parameters
    ----------
    initial : dict
        The form's initial values, updated in place.
    current : `goats_tom.models.AntaresStreamSubscription`
        The saved subscription to read from.

    Notes
    -----
    Shared by both re-render paths. They diverged once, and the draft path --
    the one taken after a failed submission -- silently dropped the template,
    which is exactly when a PI is least able to spot it.
    """
    initial["gpp_program_id"] = current.gpp_program_id
    initial["gpp_observation_id"] = current.gpp_observation_id
    initial["gpp_workflow_state"] = current.gpp_workflow_state
    initial["gpp_target_id"] = current.gpp_target_id
    initial["gpp_instrument"] = current.gpp_instrument
    if current.gpp_target_overrides:
        initial["gpp_target_overrides"] = json.dumps(
            current.gpp_target_overrides
        )
    if current.gpp_observation_overrides:
        initial["gpp_observation_overrides"] = json.dumps(
            current.gpp_observation_overrides
        )


def _save_draft(subscription: AntaresStreamSubscription, request, error: str) -> None:
    """Persist a failed submission's raw values and error message as a
    draft, so they survive navigating away and back.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        The row to save the draft onto (created if none existed yet).
    request : `HttpRequest`
        The POST request whose raw (unvalidated) values to save.
    error : str
        The validation error message to show, via the same banner used
        for runtime handler failures.
    """
    subscription.draft_topics = request.POST.get("topics", "")
    subscription.draft_consumer_group = request.POST.get("consumer_group", "")
    subscription.draft_save_all_targets = bool(request.POST.get("save_all_targets"))
    subscription.draft_trigger_gemini_observations = bool(
        request.POST.get("trigger_gemini_observations")
    )
    subscription.draft_handler_code = request.POST.get("handler_code", "")
    subscription.draft_error = error
    subscription.draft_error_at = timezone.now()
    subscription.save()


def _clear_draft(subscription: AntaresStreamSubscription) -> None:
    """Clear any saved draft, e.g. after a successful submission.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        The row whose draft fields to clear.
    """
    subscription.draft_topics = ""
    subscription.draft_consumer_group = ""
    subscription.draft_save_all_targets = False
    subscription.draft_trigger_gemini_observations = False
    subscription.draft_handler_code = ""
    subscription.draft_error = ""
    subscription.draft_error_at = None
    subscription.save()


def _requested_subscription_id(request):
    """Read an explicitly requested dashboard id from the query string.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    int or None
        The requested subscription's primary key, or `None` if absent or
        malformed. A malformed value resolves to `None` rather than being
        ignored, so it cannot silently fall through to a different dashboard.
    """
    raw = request.GET.get("subscription")
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _render_read_only(request, subscription):
    """Render the ingestion page as a read-only view of somebody else's setup.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription to display. Access has already been checked by
        `goats_tom.antares_access.get_subscription_for_view`.

    Returns
    -------
    `HttpResponse`
        The rendered page, with no form and no controls.

    Notes
    -----
    Shows the same configuration the dashboard's status banner already
    exposes -- topics, consumer group, handler code, running state and any
    error -- so the two are consistent. Previously a member could read the
    PI's handler source out of an error banner while the page that properly
    presents it was hidden from them.

    Deliberately passes no form at all rather than a disabled one: a disabled
    form still posts if the attribute is stripped client-side, and the view
    would then have to re-check permissions anyway. No form, no POST handling,
    nothing to bypass.
    """
    return render(
        request,
        "antares_stream_subscribe.html",
        {
            "form": None,
            "current": subscription,
            "read_only": True,
            "available_dashboards": list(
                accessible_subscriptions(request.user).select_related("owner")
            ),
        },
    )


@login_required
def antares_stream_subscribe(request):
    """Show and handle the "Ingest from Kafka stream" subscription form.

    On GET, shows the form pre-filled with a saved draft (a previous
    submission that failed validation, so the attempt isn't lost across
    navigation) if one exists, otherwise the current live subscription.
    On POST:

    - If the "Start ingesting" button was used (``action=start``),
      validates the form. On success, clears any draft, aborts any
      previously-running consumer, and starts a new one with the
      submitted topics and handler code (see
      `goats_tom.antares_stream_control.restart_antares_stream`). On
      failure, saves the raw submitted values and error message as a
      draft (see `_save_draft`) and re-renders the form with the error
      shown in the same banner used for runtime handler failures.
    - If the "Stop ingestion" button was used (``action=stop``), aborts
      the running consumer without starting a new one (see
      `goats_tom.antares_stream_control.stop_antares_stream`), skipping
      form validation since no new topics/handler are needed to stop.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered subscription page, or a redirect back to it after a
        successful start/stop.

    """
    # The user's own subscription, if they have one. Owning it is what
    # allows configuring, starting and stopping -- see
    # `goats_tom.antares_access.can_configure`.
    current = AntaresStreamSubscription.objects.filter(owner=request.user).first()

    # A member of somebody else's PI group has no subscription of their own,
    # but should still be able to *see* how the dashboard they can view is
    # configured -- which topics feed it, whether a handler is filtering, and
    # whether ingestion is actually running. Without this the page was a blank
    # form, which was both unhelpful and dangerous: submitting it created a
    # subscription owned by the member, silently turning them into a PI whose
    # consumer could not start for lack of their own credentials.
    # `?mine=1` forces the user's own setup page even when they have no
    # subscription yet. Without it, a member of somebody else's PI group can
    # never reach their own: the read-only branch below always intercepts.
    # That page is where the instructions for storing ANTARES credentials
    # live, so a member who later obtains their own API key would otherwise
    # have nowhere to learn what to do with it. Linked from the ANTARES
    # broker query page (see `goats_tom.brokers.antares`).
    wants_own_page = request.GET.get("mine") == "1"

    if current is None and not wants_own_page:
        viewing = get_subscription_for_view(
            request.user, _requested_subscription_id(request)
        )
        if viewing is not None:
            return _render_read_only(request, viewing)

    if request.method == "POST" and request.POST.get("action") == "stop":
        stop_antares_stream(request.user)
        messages.success(request, "ANTARES Kafka stream consumer stopped.")
        return redirect("antares-stream-subscribe")

    if request.method == "POST":
        # Clear any banner from a previous attempt up front, before doing
        # anything else. Otherwise a stale error/warning stays on screen
        # and there's no way to tell whether it came from this submission
        # or an earlier one -- particularly for `last_handler_warning`,
        # which is otherwise only cleared asynchronously by the actor once
        # it has actually started (see `_clear_stale_handler_warning`), so
        # it would linger through the redirect. Whatever happens next
        # (validation failure, or a real runtime failure) writes fresh
        # state, so nothing that's still true gets lost.
        if current is not None:
            current.last_handler_warning = ""
            current.last_handler_warning_at = None
            current.draft_error = ""
            current.draft_error_at = None
            current.save(
                update_fields=[
                    "last_handler_warning",
                    "last_handler_warning_at",
                    "draft_error",
                    "draft_error_at",
                ]
            )

        form = AntaresStreamSubscribeForm(request.POST, user=request.user)
        if form.is_valid():
            topics = form.cleaned_data["topics"]
            consumer_group = form.cleaned_data["consumer_group"]
            save_all_targets = form.cleaned_data["save_all_targets"]
            trigger_gemini_observations = form.cleaned_data[
                "trigger_gemini_observations"
            ]
            handler_code = form.cleaned_data["handler_code"]
            subscription = restart_antares_stream(
                request.user,
                topics,
                consumer_group=consumer_group,
                save_all_targets=save_all_targets,
                trigger_gemini_observations=trigger_gemini_observations,
                handler_code=handler_code,
                gpp_program_id=form.cleaned_data.get("gpp_program_id", ""),
                gpp_observation_id=form.cleaned_data.get("gpp_observation_id", ""),
                max_triggers=form.cleaned_data.get("max_triggers"),
                max_loci=form.cleaned_data.get("max_loci"),
                gpp_observation_overrides=form.cleaned_data.get(
                    "gpp_observation_overrides"
                )
                or {},
                gpp_target_overrides=form.cleaned_data.get(
                    "gpp_target_overrides"
                )
                or {},
                gpp_target_id=form.cleaned_data.get("gpp_target_id") or "",
                gpp_instrument=form.cleaned_data.get("gpp_instrument") or "",
                gpp_workflow_state=form.cleaned_data.get("gpp_workflow_state")
                or "",
            )
            _clear_draft(subscription)
            messages.success(
                request,
                f"ANTARES Kafka stream consumer requested for topics: "
                f"{', '.join(topics)}.",
            )
            return redirect("antares-stream-subscribe")
        else:
            # Collect all field errors into one message for the unified
            # banner, rather than relying on crispy's separate inline
            # per-field error rendering -- so a validation failure looks
            # and feels the same as a runtime handler failure. No
            # field-label prefixes, to match the plain style of
            # last_handler_warning (the runtime banner).
            error_lines = [
                str(err)
                for field_errors in form.errors.values()
                for err in field_errors
            ]
            error_message = "\n".join(error_lines)

            # A draft has to be saved against a real row, so create one
            # for this user if they have never successfully started a
            # subscription -- otherwise their failed attempt (and the
            # handler code they are mid-way through debugging) is lost on
            # navigation, which is the whole point of the draft fields.
            subscription = current or AntaresStreamSubscription(owner=request.user)
            _save_draft(subscription, request, error_message)
            current = subscription
    else:
        initial = {}
        if current is not None:
            has_draft = bool(
                current.draft_topics
                or current.draft_handler_code
                or current.draft_error
            )
            if has_draft:
                initial["topics"] = current.draft_topics
                initial["consumer_group"] = current.draft_consumer_group
                initial["save_all_targets"] = current.draft_save_all_targets
                initial["trigger_gemini_observations"] = (
                    current.draft_trigger_gemini_observations
                )
                initial["handler_code"] = current.draft_handler_code
                # The template comes from the saved subscription, not the
                # draft, which does not carry it. Omitting it re-rendered the
                # hidden fields empty, so the next submit posted a blank
                # template -- and with triggering on that fails validation,
                # saves another draft, and drops it again. A PI could not
                # escape without noticing they had to re-pick the template,
                # with nothing on screen saying so.
                _apply_template_initial(initial, current)
            else:
                initial["topics"] = ", ".join(current.topics)
                initial["consumer_group"] = current.consumer_group
                initial["save_all_targets"] = current.save_all_targets
                initial["trigger_gemini_observations"] = (
                    current.trigger_gemini_observations
                )
                initial["max_triggers"] = current.max_triggers
                initial["max_loci"] = current.max_loci
                _apply_template_initial(initial, current)
                initial["handler_code"] = current.handler_code
        form = AntaresStreamSubscribeForm(initial=initial, user=request.user)

    return render(
        request,
        "antares_stream_subscribe.html",
        {
            "form": form,
            "current": current,
            "read_only": False,
            # For the JS that refills an emptied cap when triggering is
            # unticked; blank means unlimited, so an empty box is a hazard
            # rather than a neutral default.
            "default_max_triggers": DEFAULT_MAX_TRIGGERS,
            # For the editor's Reset button; defined once on the form
            # so the button restores exactly what a new subscription
            # starts with, rather than a copy that could drift.
            "handler_code_skeleton": AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON,
            # Supplied even for owners: a PI who is also a member of another
            # PI's group needs the switcher too.
            "available_dashboards": list(
                accessible_subscriptions(request.user).select_related("owner")
            ),
        },
    )


@login_required
def antares_stream_status(request):
    """Render just the status box and error banners, for htmx polling.

    The actor that actually starts/stops ingestion runs asynchronously in
    a Dramatiq worker, not synchronously as part of the form submission --
    `.send()` only enqueues it, and the redirect after a successful POST
    completes before the actor has necessarily run at all. The page
    rendered right after that redirect is a single, static server-render:
    it reflects whatever `AntaresStreamSubscription` looked like at that
    exact moment, and nothing on it re-queries the database afterward, so
    if the actor's first real update (e.g. recording a startup failure)
    lands even a fraction of a second later, the page silently misses it
    until some other navigation triggers a fresh render. Polled from the
    main page via htmx (see `antares_stream_subscribe.html`) so the status
    catches up on its own instead of requiring a manual reload or
    navigating away and back.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered status partial.

    """
    # Resolve the same subscription the page itself is showing. Scoping this
    # to the requesting user's own subscription meant a member viewing a PI's
    # configuration got an empty banner back three seconds later -- the status
    # appeared on load and then silently vanished.
    current = AntaresStreamSubscription.objects.filter(owner=request.user).first()
    read_only = False

    # `mine=1` means the page is the user's OWN setup page, so the banner must
    # report only their own subscription -- nothing, if they have none.
    # Without this the fallback below filled a member's own (blank) setup page
    # with the PI's topics, running state and warnings three seconds after
    # load: the page rendered correctly, then this poll overwrote it.
    if current is None and request.GET.get("mine") != "1":
        current = get_subscription_for_view(
            request.user, _requested_subscription_id(request)
        )
        read_only = current is not None

    return render(
        request,
        "partials/antares_stream_status.html",
        {"current": current, "read_only": read_only},
    )


@login_required
def antares_available_topics(request):
    """Return available ANTARES Kafka topics as JSON, fetched live.

    Called via JS only when the user actually interacts with the topics
    field (see the template), not automatically on page load -- so a
    real Kafka connection (SASL handshake, broker round-trip) only
    happens when someone genuinely wants to see the topic list, not on
    every visit to this page. Not cached: since this is now on-demand
    rather than automatic, the cost of a live fetch each time is small,
    and it means a topic added or removed on the broker shows up
    immediately rather than waiting for a cache entry to expire.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `JsonResponse`
        ``{"topics": [...]}`` on success, or ``{"topics": [], "error":
        "..."}`` if the fetch failed (e.g. no credentials stored, broker
        unreachable) -- still a 200 response either way, since an empty
        dropdown with an explanatory message is a normal, handled
        outcome for this endpoint, not a server error.

    """
    try:
        topics = fetch_available_topics(request.user)
    except TopicListError as exc:
        logger.warning("Could not fetch available ANTARES topics: %s", exc)
        return JsonResponse({"topics": [], "error": str(exc)})

    return JsonResponse({"topics": topics})
