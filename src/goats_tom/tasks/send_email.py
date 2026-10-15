"""Background tasks that send the emails queued in `goats_tom.outbox`."""

__all__ = ["send_email", "retry_emails"]

import logging
from datetime import datetime, timedelta

import dramatiq
from django.core.mail import EmailMultiAlternatives
from django.db.models import F
from django.utils import timezone

from goats_scheduler.scheduling import cron
from goats_tom.models import OutgoingEmail
from goats_tom.outbox import email_enabled

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
"""How many times an email is tried before giving up."""

RETRY_AFTER = timedelta(minutes=5)
"""How old an unsent email must be before the sweep re-queues it."""


# No dramatiq retries: `retry_emails` is the only retry path, so a failing email
# is never retried by two mechanisms at once.
@dramatiq.actor(max_retries=0)
def send_email(email_id: int) -> None:
    """Send a queued email, at most once.

    Parameters
    ----------
    email_id : int
        Primary key of the `goats_tom.models.OutgoingEmail`.
    """
    # Claimed before sending, so concurrent workers cannot both send it.
    claimed_at = timezone.now()
    claim = OutgoingEmail.objects.filter(
        pk=email_id, sent_at__isnull=True, attempts__lt=MAX_ATTEMPTS
    )
    if not claim.update(sent_at=claimed_at, attempts=F("attempts") + 1):
        return

    email = OutgoingEmail.objects.get(pk=email_id)
    try:
        _send(email)
    except Exception:
        _release(email_id, claimed_at)
        logger.exception("Could not send email %s.", email_id)
        return
    except BaseException:
        # Interrupted, e.g. by dramatiq's time limit: still retried by the sweep.
        _release(email_id, claimed_at)
        raise
    # Not kept once sent: a body can hold a password reset link.
    OutgoingEmail.objects.filter(pk=email_id).update(body="", html="")
    logger.info("Sent email %s.", email_id)


@cron(minute="*/10")
@dramatiq.actor(max_retries=0)
def retry_emails() -> None:
    """Re-queue emails whose send failed or that never reached the broker."""
    if not email_enabled():
        return
    due = OutgoingEmail.objects.filter(
        sent_at__isnull=True,
        attempts__lt=MAX_ATTEMPTS,
        created_at__lte=timezone.now() - RETRY_AFTER,
    ).values_list("pk", flat=True)
    for pk in due:
        send_email.send(pk)


def _release(email_id: int, claimed_at: datetime) -> None:
    """Undo a claim, so `retry_emails` picks the email up again.

    Parameters
    ----------
    email_id : int
        Primary key of the `OutgoingEmail`.
    claimed_at : `datetime.datetime`
        The claim to undo; a newer one is left alone.
    """
    OutgoingEmail.objects.filter(pk=email_id, sent_at=claimed_at).update(sent_at=None)


def _send(email: OutgoingEmail) -> None:
    """Send `email` through Django's email backend.

    Parameters
    ----------
    email : `OutgoingEmail`
        The email to send.
    """
    message = EmailMultiAlternatives(
        subject=email.subject, body=email.body, to=[email.to]
    )
    if email.html:
        message.attach_alternative(email.html, "text/html")
    message.send()
