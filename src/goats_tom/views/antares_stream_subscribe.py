__all__ = ["antares_stream_subscribe"]

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from goats_tom.antares_stream_control import restart_antares_stream, stop_antares_stream
from goats_tom.forms import AntaresStreamSubscribeForm
from goats_tom.models import AntaresStreamSubscription


@login_required
def antares_stream_subscribe(request):
    """Show and handle the "Ingest from Kafka stream" subscription form.

    On GET, shows the form pre-filled with the current subscription (if
    any). On POST:

    - If the "Start ingesting" button was used (``action=start``),
      validates the form, aborts any previously-running consumer, and
      starts a new one with the submitted topics and handler code (see
      `goats_tom.antares_stream_control.restart_antares_stream`).
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
            save_all_targets = form.cleaned_data["save_all_targets"]
            trigger_gemini_observations = form.cleaned_data[
                "trigger_gemini_observations"
            ]
            handler_code = form.cleaned_data["handler_code"]
            restart_antares_stream(
                topics,
                save_all_targets=save_all_targets,
                trigger_gemini_observations=trigger_gemini_observations,
                handler_code=handler_code,
            )
            messages.success(
                request,
                f"ANTARES Kafka stream consumer (re)started for topics: "
                f"{', '.join(topics)}",
            )
            return redirect("antares-stream-subscribe")
    else:
        initial = {}
        if current is not None:
            initial["topics"] = ", ".join(current.topics)
            initial["save_all_targets"] = current.save_all_targets
            initial["trigger_gemini_observations"] = (
                current.trigger_gemini_observations
            )
            initial["handler_code"] = current.handler_code
        form = AntaresStreamSubscribeForm(initial=initial)

    return render(
        request,
        "antares_stream_subscribe.html",
        {"form": form, "current": current},
    )
