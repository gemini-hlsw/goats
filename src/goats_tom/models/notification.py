"""Module for `Notification` model."""

__all__ = ["Notification"]

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    """One message addressed to one user, kept until they read it.

    Created only through `goats_tom.notifications.notify`, which also pushes it
    live and emails it. The text is stored as rendered, so the inbox still reads
    correctly after the object it is about has gone.

    Attributes
    ----------
    recipient : `models.ForeignKey`
        Who it is for.
    kind : `models.CharField`
        Key of the `goats_tom.notifications.kinds.NotificationKind` it was built
        from.
    title : `models.CharField`
        Short heading.
    message : `models.TextField`
        One or two sentences, plain text.
    detail : `models.TextField`
        Optional longer explanation, shown on the inbox page and in the email.
    url : `models.CharField`
        Site-relative path to act on it, or empty.
    actor : `models.ForeignKey`
        Who caused it, if anyone. `SET_NULL` so the message outlives the account.
    subject_type, subject_id : generic relation
        What it is about, so it can be resolved once someone acts on it.
    created_at : `models.DateTimeField`
        When it was created.
    read_at : `models.DateTimeField`
        When it was read or resolved. `None` while unread.
    email_pending : `models.BooleanField`
        Whether an email is owed, decided once at creation. Lets the periodic
        sweep re-queue emails that never reached the broker.
    email_attempts : `models.PositiveSmallIntegerField`
        How many times sending was attempted, so a failing address gives up.
    emailed_at : `models.DateTimeField`
        When the email was claimed for sending. Set before the send, so a
        concurrent or retried task never sends it twice.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    message = models.TextField()
    detail = models.TextField(blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_caused",
    )
    subject_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    subject_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_pending = models.BooleanField(default=False)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["subject_type", "subject_id"]),
            models.Index(
                fields=["created_at"],
                condition=models.Q(email_pending=True, emailed_at__isnull=True),
                name="notification_email_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} for {self.recipient_id}"

    @property
    def is_read(self) -> bool:
        """Whether the recipient has read it or it no longer needs them."""
        return self.read_at is not None
