"""Module for `RegistrationRequest` model."""

__all__ = ["RegistrationRequest"]

from django.conf import settings
from django.db import models


class RegistrationRequest(models.Model):
    """A self-registered account waiting for an administrator's decision.

    Registration creates the `django.contrib.auth.models.User` immediately but
    with ``is_active = False``, and records this row alongside it. An inactive
    user cannot sign in, so the account is harmless until approved, while
    still reserving the username and letting the person set their own password
    rather than having one mailed to them.

    Approval simply flips ``is_active``. Rejection deactivates permanently and
    keeps the record, so an administrator can see they have already answered
    and the same person cannot silently re-apply into an empty queue.

    This table -- not a notification -- is the source of truth. Administrators
    are notified in real time when a request arrives (see
    `goats_tom.realtime`), but that only reaches connected sessions, so
    anything depending on it would lose requests made while nobody was logged
    in.

    Attributes
    ----------
    user : `models.OneToOneField`
        The account created by the registration form, inactive until
        approved. `CASCADE`: deleting the account removes the request with it.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED`, `STATUS_REJECTED`.
    requested_groups : `models.ManyToManyField`
        Groups the applicant asked to join. Deliberately *requested* rather
        than assigned: the form is public, so anyone could otherwise put
        themselves into a group and gain access to whatever that group shares
        the moment they were approved. Recording the request separately means
        an administrator sees what was asked for and decides what to grant --
        and the two stay distinguishable afterwards if they grant less.
    reason : `models.TextField`
        Optional note from the applicant -- which programme or collaboration
        they are with. An administrator approving an unfamiliar username
        otherwise has nothing to go on.
    decided_by : `models.ForeignKey`
        Which administrator decided it. `SET_NULL` so deleting that account
        loses the attribution rather than the decision itself.
    decided_at : `models.DateTimeField`
        When the decision was made. `None` while pending.
    created_at : `models.DateTimeField`
        When the person registered. Used to order the queue oldest first, so
        requests cannot be left behind newer ones indefinitely.

    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registration_request",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    requested_groups = models.ManyToManyField(
        "auth.Group",
        blank=True,
        related_name="registration_requests",
    )
    reason = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registration request"
        verbose_name_plural = "registration requests"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.status})"
