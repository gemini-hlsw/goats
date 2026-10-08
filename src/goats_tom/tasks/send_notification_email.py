"""Background task that emails one notification."""

__all__ = ["send_notification_email", "retry_notification_emails"]

import logging
from datetime import timedelta

import dramatiq
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from goats_scheduler.scheduling import cron
from goats_tom.models import Notification

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
"""How many times an email is tried before giving up."""

RETRY_AFTER = timedelta(minutes=5)
"""How old an unsent email must be before the sweep re-queues it."""


def _absolute(path: str) -> str:
    """Prefix `path` with ``GOATS_SITE_URL``, or return "" when it is unset."""
    base = getattr(settings, "GOATS_SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base and path else ""


# No dramatiq retries: `retry_notification_emails` is the only retry path, so a
# failing email is never retried by two mechanisms at once.
@dramatiq.actor(max_retries=0)
def send_notification_email(notification_id: int) -> None:
    """Email a notification to its recipient, at most once.

    The notification is claimed by setting `emailed_at` in one conditional
    update before sending, so concurrent workers cannot both send it. A failed
    send releases the claim for `retry_notification_emails` to pick up. If the
    worker dies between claiming and sending, the email is lost rather than sent
    twice; the notification itself stays in the inbox.

    Parameters
    ----------
    notification_id : int
        Primary key of the `goats_tom.models.Notification`.
    """
    notification = (
        Notification.objects.select_related("recipient")
        .filter(pk=notification_id)
        .first()
    )
    if notification is None or not notification.recipient.email:
        return

    claimed_at = timezone.now()
    claim = Notification.objects.filter(
        pk=notification.pk,
        email_pending=True,
        emailed_at__isnull=True,
        email_attempts__lt=MAX_ATTEMPTS,
    )
    if not claim.update(emailed_at=claimed_at, email_attempts=F("email_attempts") + 1):
        return

    try:
        _send(notification)
    except Exception:
        Notification.objects.filter(pk=notification.pk, emailed_at=claimed_at).update(
            emailed_at=None
        )
        logger.exception("Could not email notification %s.", notification.pk)
        return
    logger.info("Emailed notification %s (%s).", notification.pk, notification.kind)


@cron(minute="*/10")
@dramatiq.actor(max_retries=0)
def retry_notification_emails() -> None:
    """Re-queue owed emails that were never sent.

    Covers both an email whose send failed and one that never reached the
    broker. Queueing one twice is harmless: `send_notification_email` claims
    each notification before sending.
    """
    if not getattr(settings, "GOATS_EMAIL_NOTIFICATIONS", False):
        return
    due = Notification.objects.filter(
        email_pending=True,
        emailed_at__isnull=True,
        email_attempts__lt=MAX_ATTEMPTS,
        created_at__lte=timezone.now() - RETRY_AFTER,
    ).values_list("pk", flat=True)
    for pk in due:
        send_notification_email.send(pk)


def _send(notification: Notification) -> None:
    """Render and send the email for `notification`."""
    context = {
        "notification": notification,
        "action_url": _absolute(notification.url),
        "inbox_url": _absolute(reverse("notifications")),
    }
    prefix = getattr(settings, "GOATS_EMAIL_SUBJECT_PREFIX", "[GOATS] ")
    email = EmailMultiAlternatives(
        subject=f"{prefix}{notification.title}",
        body=render_to_string("notifications/email.txt", context),
        to=[notification.recipient.email],
    )
    email.attach_alternative(
        render_to_string("notifications/email.html", context), "text/html"
    )
    email.send()
