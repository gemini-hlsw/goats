__all__ = [
    "antares_stream_subscribe",
    "antares_stream_status",
    "antares_available_topics",
]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from goats_tom.antares_stream_control import (
    TopicListError,
    fetch_available_topics,
    restart_antares_stream,
    stop_antares_stream,
)
from goats_tom.forms import AntaresStreamSubscribeForm
from goats_tom.models import AntaresStreamSubscription

logger = logging.getLogger(__name__)


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
    subscription.draft_group = request.POST.get("group", "")
    subscription.draft_save_all_targets = bool(request.POST.get("save_all_targets"))
    subscription.draft_trigger_gemini_observations = bool(
        request.POST.get("trigger_gemini_observations")
    )
    subscription.draft_handler_code = request.POST.get("handler_code", "")
    subscription.draft_error = error
    subscription.save()


def _clear_draft(subscription: AntaresStreamSubscription) -> None:
    """Clear any saved draft, e.g. after a successful submission.

    Parameters
    ----------
    subscription : `AntaresStreamSubscription`
        The row whose draft fields to clear.
    """
    subscription.draft_topics = ""
    subscription.draft_group = ""
    subscription.draft_save_all_targets = False
    subscription.draft_trigger_gemini_observations = False
    subscription.draft_handler_code = ""
    subscription.draft_error = ""
    subscription.save()


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
    current = AntaresStreamSubscription.objects.order_by("-updated_at").first()

    if request.method == "POST" and request.POST.get("action") == "stop":
        stop_antares_stream()
        messages.success(request, "ANTARES Kafka stream consumer stopped.")
        return redirect("antares-stream-subscribe")

    if request.method == "POST":
        form = AntaresStreamSubscribeForm(request.POST)
        if form.is_valid():
            topics = form.cleaned_data["topics"]
            group = form.cleaned_data["group"]
            save_all_targets = form.cleaned_data["save_all_targets"]
            trigger_gemini_observations = form.cleaned_data[
                "trigger_gemini_observations"
            ]
            handler_code = form.cleaned_data["handler_code"]
            subscription = restart_antares_stream(
                topics,
                group=group,
                save_all_targets=save_all_targets,
                trigger_gemini_observations=trigger_gemini_observations,
                handler_code=handler_code,
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

            subscription = current or AntaresStreamSubscription()
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
                initial["group"] = current.draft_group
                initial["save_all_targets"] = current.draft_save_all_targets
                initial["trigger_gemini_observations"] = (
                    current.draft_trigger_gemini_observations
                )
                initial["handler_code"] = current.draft_handler_code
            else:
                initial["topics"] = ", ".join(current.topics)
                initial["group"] = current.group
                initial["save_all_targets"] = current.save_all_targets
                initial["trigger_gemini_observations"] = (
                    current.trigger_gemini_observations
                )
                initial["handler_code"] = current.handler_code
        form = AntaresStreamSubscribeForm(initial=initial)

    return render(
        request,
        "antares_stream_subscribe.html",
        {
            "form": form,
            "current": current,
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
    current = AntaresStreamSubscription.objects.order_by("-updated_at").first()
    return render(
        request,
        "partials/antares_stream_status.html",
        {"current": current},
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
        topics = fetch_available_topics()
    except TopicListError as exc:
        logger.warning("Could not fetch available ANTARES topics: %s", exc)
        return JsonResponse({"topics": [], "error": str(exc)})

    return JsonResponse({"topics": topics})
