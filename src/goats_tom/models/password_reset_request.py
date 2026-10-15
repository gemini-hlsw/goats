"""Module for `PasswordResetRequest` model."""

__all__ = ["PasswordResetRequest"]

from django.conf import settings
from django.db import models


class PasswordResetRequest(models.Model):
    """A request to reset a forgotten password, decided by an administrator.

    Attributes
    ----------
    user : `models.ForeignKey`
        The account to reset.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED` (a temporary password was
        set and must be changed at the next sign-in), `STATUS_DENIED`,
        `STATUS_COMPLETED` (the user chose a new password).
    decided_by : `models.ForeignKey`
        The administrator who decided it.
    decided_at : `models.DateTimeField`
        When it was decided. `None` while pending.
    created_at : `models.DateTimeField`
        When it was made.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
        (STATUS_COMPLETED, "Completed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="password_reset_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "password reset request"
        verbose_name_plural = "password reset requests"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="pending"),
                name="unique_pending_password_reset_request",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.status})"
