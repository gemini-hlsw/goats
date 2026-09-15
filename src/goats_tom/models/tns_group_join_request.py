"""Module for `TNSGroupJoinRequest` model."""

__all__ = ["TNSGroupJoinRequest"]

from django.conf import settings
from django.db import models


class TNSGroupJoinRequest(models.Model):
    """A user's request to post through somebody else's TNS group.

    Deliberately the same shape as
    `goats_tom.models.AntaresGroupJoinRequest`, for the same reasons: this
    table, not a notification, is the source of truth. An owner is told in
    real time when a request arrives and again by email, but neither is
    durable in the way a row is -- the toast reaches only connected
    sessions, and mail can bounce. The pending queue is rendered from these
    rows, so a missed message costs immediacy and nothing else.

    Requests are per-group rather than per-owner. An owner may run one bot
    across several collaborations and be willing to share one of them,
    which an all-or-nothing request could not express.

    Decided requests are kept rather than deleted, so an owner can see they
    have already answered somebody and a requester can see their request
    was decided rather than lost.

    Attributes
    ----------
    requester : `models.ForeignKey`
        The user asking to post through the group. `CASCADE`: a deleted
        account's requests should not sit undecidable in a queue.
    tns_group : `models.ForeignKey`
        The group being asked for. `CASCADE` for the same reason.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED`, `STATUS_DENIED`.
    message : `models.TextField`
        Optional note from the requester. An owner deciding whether to let
        an unfamiliar username post under their bot's name otherwise has
        nothing to go on, and this decision is more consequential than most
        -- TNS attributes the post to the owner's bot, not the requester.
    decided_by : `models.ForeignKey`
        Who approved or denied it -- normally the owner, but a superuser
        may also act. `SET_NULL`, so deleting that account loses the
        attribution rather than the record of the decision.
    decided_at : `models.DateTimeField`
        When it was decided. `None` while pending.
    created_at : `models.DateTimeField`
        When it was made. Orders the owner's queue oldest first, so nothing
        is left indefinitely behind newer requests.

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
            # At most one *pending* request per (requester, group). A plain
            # unique_together would permanently bar anyone who was ever
            # denied from asking again, and deleting denied rows to work
            # around that would erase the decision history.
            models.UniqueConstraint(
                fields=["requester", "tns_group"],
                condition=models.Q(status="pending"),
                name="unique_pending_tns_join_request",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.requester.username} -> {self.tns_group.name} "
            f"({self.status})"
        )
