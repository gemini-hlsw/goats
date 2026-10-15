"""Module for `OutgoingEmail` model."""

__all__ = ["OutgoingEmail"]

from django.db import models


class OutgoingEmail(models.Model):
    """One email GOATS sends, rendered when queued and kept until sent.

    Attributes
    ----------
    to : `models.EmailField`
        The recipient's address.
    subject : `models.CharField`
        Subject line, prefix included.
    body : `models.TextField`
        Plain-text body, cleared once sent.
    html : `models.TextField`
        HTML body, or empty. Cleared once sent.
    created_at : `models.DateTimeField`
        When it was queued.
    attempts : `models.PositiveSmallIntegerField`
        How many times sending was attempted, so a failing address gives up.
    sent_at : `models.DateTimeField`
        When it was claimed for sending, set before the send so it never goes
        out twice. `None` while unsent.
    """

    to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    html = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "outgoing email"
        verbose_name_plural = "outgoing emails"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["created_at"],
                condition=models.Q(sent_at__isnull=True),
                name="outgoing_email_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subject} to {self.to}"
