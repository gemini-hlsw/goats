from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
@require_GET
def status_view(request: HttpRequest) -> HttpResponse:
    """
    Renders the service status dashboard page.

    Returns
    -------
    HttpResponse
        HTML response with embedded JavaScript that fetches status info.
    """
    return render(request, "status.html")
