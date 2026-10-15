"""Queue the emails GOATS sends; `goats_tom.tasks.send_email` sends them."""

__all__ = ["email_enabled", "queue_email", "site_url"]

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string

from goats_tom.models import OutgoingEmail

logger = logging.getLogger(__name__)


def email_enabled() -> bool:
    """Whether this instance sends email, set by ``GOATS_SEND_EMAIL``."""
    return getattr(settings, "GOATS_SEND_EMAIL", False)


def site_url(path: str) -> str:
    """Make `path` absolute with ``GOATS_SITE_URL``, for links in emails.

    Parameters
    ----------
    path : str
        Site-relative path.

    Returns
    -------
    str
        The absolute URL, or "" without a site URL or a path.
    """
    base = getattr(settings, "GOATS_SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base and path else ""


def queue_email(
    to: str, subject: str, template: str, context: dict[str, Any]
) -> OutgoingEmail | None:
    """Render an email and queue it to be sent once the transaction commits.

    Parameters
    ----------
    to : str
        The recipient's address.
    subject : str
        Subject line, without ``GOATS_EMAIL_SUBJECT_PREFIX``.
    template : str
        Template path without extension; its ``.txt`` and ``.html`` are rendered.
    context : dict[str, Any]
        Template context.

    Returns
    -------
    `OutgoingEmail` or None
        The queued email, or `None` when email is off or there is no address.
    """
    if not to or not email_enabled():
        return None

    prefix = getattr(settings, "GOATS_EMAIL_SUBJECT_PREFIX", "[GOATS] ")
    email = OutgoingEmail.objects.create(
        to=to,
        subject=f"{prefix}{subject}",
        body=render_to_string(f"{template}.txt", context),
        html=render_to_string(f"{template}.html", context),
    )
    transaction.on_commit(lambda: _enqueue(email.pk))
    return email


def _enqueue(email_id: int) -> None:
    """Hand an email to the worker, leaving it to the sweep if the broker is down.

    Parameters
    ----------
    email_id : int
        Primary key of the `OutgoingEmail`.
    """
    # Deferred: `goats_tom.tasks` imports modules that import this one.
    from goats_tom.tasks import send_email  # noqa: PLC0415

    try:
        send_email.send(email_id)
    except Exception:
        logger.exception("Could not queue email %s.", email_id)
