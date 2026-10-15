"""Module for `AccountRequest` model."""

__all__ = ["AccountRequest"]

from django.conf import settings
from django.db import models


class AccountRequest(models.Model):
    """A request for a GOATS account and the administrator's decision on it.

    Attributes
    ----------
    user : `models.OneToOneField`
        The account, inactive until approved. `None` once denied, since denying
        deletes it.
    username, full_name, email : `models.CharField`, `models.EmailField`
        Copied from the account, so a denied request still says who asked.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED`, `STATUS_DENIED`.
    message : `models.TextField`
        Optional note from the applicant.
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
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_request",
    )
    username = models.CharField(max_length=150)
    full_name = models.CharField(max_length=301, blank=True, default="")
    email = models.EmailField()
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    message = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "account request"
        verbose_name_plural = "account requests"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.username} ({self.status})"
