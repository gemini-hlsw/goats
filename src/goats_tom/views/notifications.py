"""Views for the signed-in user's notification inbox."""

__all__ = [
    "notification_list",
    "notification_open",
    "notification_mark_all_read",
]

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from goats_tom.models import Notification
from goats_tom.notifications import mark_all_read, mark_read


@login_required
def notification_list(request: HttpRequest) -> HttpResponse:
    """Show the user's notifications, newest first.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered inbox.
    """
    notifications = Notification.objects.filter(recipient=request.user)
    page_obj = Paginator(notifications, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "notifications/list.html",
        {
            "page_obj": page_obj,
            "has_unread": notifications.filter(read_at__isnull=True).exists(),
        },
    )


@login_required
def notification_open(request: HttpRequest, pk: int) -> HttpResponse:
    """Mark a notification as read and go to the page it points at.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.
    pk : int
        Primary key of the notification. Another user's returns 404.

    Returns
    -------
    `HttpResponse`
        Redirect to the notification's link, or to the inbox if it has none.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    mark_read(notification)
    if notification.url and url_has_allowed_host_and_scheme(
        notification.url, allowed_hosts={request.get_host()}
    ):
        return redirect(notification.url)
    return redirect("notifications")


@login_required
@require_POST
def notification_mark_all_read(request: HttpRequest) -> HttpResponse:
    """Mark every notification of the user as read.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        Redirect to the inbox.
    """
    if mark_all_read(request.user):
        messages.success(request, "All notifications marked as read.")
    return redirect("notifications")
