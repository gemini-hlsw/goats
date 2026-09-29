"""Module for `TNSGroupJoinRequest` model."""

__all__ = ["TNSGroupJoinRequest"]

from django.conf import settings
from django.db import models


class TNSGroupJoinRequest(models.Model):
    """A user's request to post through somebody else's TNS group.

    This table, not the toast or the email, is the source of truth: the
    owner's queue is rendered from these rows, so a missed message costs
    immediacy and nothing else. Decided requests are kept rather than
    deleted, so both sides can see a request was answered.

    Attributes
    ----------
    requester : `models.ForeignKey`
        The user asking to post through the group.
    tns_group : `models.ForeignKey`
        The group being asked for. Per-group rather than per-owner, since
        an owner may share one collaboration and not another.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED`, `STATUS_DENIED`.
    message : `models.TextField`
        Optional note from the requester, since TNS attributes the post to
        the owner's bot and an unfamiliar username is little to go on.
    decided_by : `models.ForeignKey`
        Who approved or denied it. `SET_NULL`, so deleting that account
        loses the attribution rather than the decision.
    decided_at : `models.DateTimeField`
        When it was decided. `None` while pending.
    created_at : `models.DateTimeField`
        When it was made. Orders the queue oldest first.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tns_join_requests",
    )
    tns_group = models.ForeignKey(
        "goats_tom.TNSGroup",
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
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
        related_name="tns_join_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "TNS group join request"
        verbose_name_plural = "TNS group join requests"
        ordering = ["created_at"]
        constraints = [
            # Only *pending* rows are constrained: a plain unique_together
            # would bar anyone once denied from ever asking again.
            models.UniqueConstraint(
                fields=["requester", "tns_group"],
                condition=models.Q(status="pending"),
                name="unique_pending_tns_join_request",
            )
        ]

    def __str__(self) -> str:
        return f"{self.requester.username} -> {self.tns_group.name} ({self.status})"
