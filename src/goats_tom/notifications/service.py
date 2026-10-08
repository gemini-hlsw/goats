"""Create, deliver and read notifications.

`notify` is the only way to send one. It stores a row per recipient and, once
the transaction commits, pushes it to their open pages and queues the email.
Delivery failures are logged and swallowed: the row is already saved, so a
down channel layer or broker costs immediacy, never the notification.
"""

__all__ = [
    "notify",
    "resolve",
    "unread_count",
    "mark_read",
    "mark_all_read",
    "serialize",
]

import logging
from collections.abc import Iterable

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from goats_tom.models import Notification
from goats_tom.realtime import InboxUpdate

from .kinds import actionable_kinds, get_kind, style

logger = logging.getLogger(__name__)


def notify(
    recipients,
    kind: str,
    *,
    actor=None,
    subject=None,
    **context,
) -> list[Notification]:
    """Send one kind of notification to one or more users.

    Parameters
    ----------
    recipients : `User` or iterable of `User`
        Who to notify. Inactive accounts and duplicates are skipped.
    kind : str
        Key of a registered `goats_tom.notifications.kinds.NotificationKind`.
    actor : `User`, optional
        Who caused it.
    subject : `models.Model`, optional
        What it is about, so `resolve` can clear it once someone acts.
    **context
        Passed to the kind's ``render``.

    Returns
    -------
    list of `goats_tom.models.Notification`
        The rows created, one per recipient.
    """
    spec = get_kind(kind)
    content = spec.render(**context)
    subject_type = ContentType.objects.get_for_model(subject) if subject else None
    email = spec.email and getattr(settings, "GOATS_EMAIL_NOTIFICATIONS", False)

    rows = [
        Notification.objects.create(
            recipient=user,
            kind=spec.key,
            title=content.title,
            message=content.message,
            detail=content.detail,
            url=content.url,
            actor=actor,
            subject_type=subject_type,
            subject_id=subject.pk if subject else None,
            email_pending=email and bool(user.email),
        )
        for user in _unique_active(recipients)
    ]
    if rows:
        transaction.on_commit(lambda: _deliver(rows))
    return rows


def resolve(subject) -> int:
    """Mark every unread actionable notification about `subject` as read.

    Parameters
    ----------
    subject : `models.Model`
        The object someone has just acted on, e.g. a decided request.

    Returns
    -------
    int
        How many notifications were resolved.
    """
    pending = Notification.objects.filter(
        subject_type=ContentType.objects.get_for_model(subject),
        subject_id=subject.pk,
        kind__in=actionable_kinds(),
        read_at__isnull=True,
    )
    read = _group_by_recipient(pending)
    if not read:
        return 0
    read_ids = [pk for pks in read.values() for pk in pks]
    resolved = Notification.objects.filter(
        pk__in=read_ids, read_at__isnull=True
    ).update(read_at=timezone.now())
    transaction.on_commit(lambda: _push_read(read))
    return resolved


def unread_count(user) -> int:
    """Number of unread notifications for `user`."""
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(notification: Notification) -> None:
    """Mark one notification as read and refresh the recipient's other pages."""
    if notification.read_at is not None:
        return
    notification.read_at = timezone.now()
    notification.save(update_fields=["read_at"])
    read = {notification.recipient_id: [notification.pk]}
    transaction.on_commit(lambda: _push_read(read))


def mark_all_read(user) -> int:
    """Mark all of `user`'s notifications as read.

    Returns
    -------
    int
        How many were unread.
    """
    read_ids = list(
        Notification.objects.filter(recipient=user, read_at__isnull=True).values_list(
            "pk", flat=True
        )
    )
    if not read_ids:
        return 0
    # Only the rows just captured: one created meanwhile was never shown.
    updated = Notification.objects.filter(pk__in=read_ids, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    read = {user.pk: read_ids}
    transaction.on_commit(lambda: _push_read(read))
    return updated


def serialize(notification: Notification) -> dict:
    """The fields the browser needs to render one notification.

    Parameters
    ----------
    notification : `goats_tom.models.Notification`
        The notification.

    Returns
    -------
    dict
        JSON-serialisable fields, including the toast colour and autohide.
    """
    try:
        actionable = get_kind(notification.kind).actionable
    except ValueError:
        # A kind removed after the row was stored still renders.
        actionable = False
    icon, color = style(notification.kind)
    return {
        "id": notification.pk,
        "title": notification.title,
        "message": notification.message,
        "color": color,
        "icon": icon,
        "autohide": not actionable,
        "created_at": notification.created_at.isoformat(),
    }


def _unique_active(recipients) -> list:
    """Active users from `recipients`, without duplicates, in order."""
    if recipients is None:
        return []
    if not isinstance(recipients, Iterable):
        recipients = [recipients]
    seen, users = set(), []
    for user in recipients:
        if user is None or not user.is_active or user.pk in seen:
            continue
        seen.add(user.pk)
        users.append(user)
    return users


def _deliver(rows: list[Notification]) -> None:
    """Push each row live and queue its email.

    A failed enqueue is only logged: the row keeps `email_pending`, so
    `goats_tom.tasks.retry_notification_emails` queues it once the broker is back.
    """
    # Deferred: `goats_tom.tasks` imports this package's callers.
    from goats_tom.tasks import send_notification_email  # noqa: PLC0415

    for row in rows:
        try:
            unread = unread_count(row.recipient_id)
            InboxUpdate.send(row.recipient_id, unread, serialize(row))
        except Exception:
            logger.exception("Could not push notification %s.", row.pk)

        if row.email_pending:
            try:
                send_notification_email.send(row.pk)
            except Exception:
                logger.exception("Could not queue email for notification %s.", row.pk)


def _group_by_recipient(notifications) -> dict[int, list[int]]:
    """Primary keys of `notifications`, grouped by recipient."""
    grouped: dict[int, list[int]] = {}
    for pk, recipient_id in notifications.values_list("pk", "recipient_id"):
        grouped.setdefault(recipient_id, []).append(pk)
    return grouped


def _push_read(read: dict[int, list[int]]) -> None:
    """Tell each user's open pages which notifications are now read."""
    for user_id, read_ids in read.items():
        try:
            InboxUpdate.send(user_id, unread_count(user_id), read_ids=read_ids)
        except Exception:
            logger.exception("Could not push read notifications to user %s.", user_id)
