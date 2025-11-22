from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def status_view(request):
    """
    Renders the service status dashboard page.

    Returns
    -------
    HttpResponse
        HTML response with embedded JavaScript that fetches status info.
    """
    return render(request, "status.html")
