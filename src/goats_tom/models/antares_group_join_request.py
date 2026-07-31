"""Module for `AntaresGroupJoinRequest` model."""

__all__ = ["AntaresGroupJoinRequest"]

from django.conf import settings
from django.db import models


class AntaresGroupJoinRequest(models.Model):
    """A user's request to join a PI's ANTARES group, awaiting a decision.

    This table -- not a notification -- is the source of truth for pending
    requests. A PI is notified in real time when one arrives (see
    `goats_tom.realtime`), but the notification is a convenience layer: it
    is delivered only to connected sessions, so anything that depended on
    it would silently lose requests made while the PI was offline. The
    queue is rendered from these rows, so a missed notification costs
    nothing but immediacy.

    Decided requests are kept rather than deleted, so a PI can see that
    they have already denied someone and a user can see that their request
    was answered rather than lost.

    Attributes
    ----------
    requester : `models.ForeignKey`
        The user asking for access. `CASCADE`: a deleted account's
        requests should not remain in a PI's queue, undecidable.
    pi_group : `models.ForeignKey`
        The group being requested. `CASCADE` for the same reason.
    status : `models.CharField`
        One of `STATUS_PENDING`, `STATUS_APPROVED`, `STATUS_DENIED`.
    requested_view_dashboard : `models.BooleanField`
        Whether the requester is asking to view the dashboard. Defaults to
        `True`: viewing is the reason to join at all.
    requested_save_targets : `models.BooleanField`
        Whether the requester is also asking to save loci as targets. What
        is *granted* is decided independently by the PI and recorded on
        `goats_tom.models.AntaresDashboardMembership` -- this field records
        only what was asked for, so a PI can approve a narrower set of
        permissions than requested without that difference being lost.
    message : `models.TextField`
        Optional note from the requester, e.g. which programme they are on.
        A PI approving a request from an unfamiliar username otherwise has
        nothing to go on.
    decided_by : `models.ForeignKey`
        Who approved or denied it -- normally the PI, but a superuser may
        also act. `SET_NULL`, so deleting that account loses the
        attribution rather than the decision record.
    decided_at : `models.DateTimeField`
        When the decision was made. `None` while pending.
    created_at : `models.DateTimeField`
        When the request was made. Used to order the PI's queue oldest
        first, so requests can't be left indefinitely behind newer ones.

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
        related_name="antares_join_requests",
    )
    pi_group = models.ForeignKey(
        "goats_tom.AntaresPIGroup",
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    requested_view_dashboard = models.BooleanField(default=True)
    requested_save_targets = models.BooleanField(default=False)
    message = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antares_join_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ANTARES group join request"
        verbose_name_plural = "ANTARES group join requests"
        ordering = ["created_at"]
        constraints = [
            # At most one *pending* request per (requester, group), while
            # still allowing a fresh request after a denial -- a plain
            # unique_together on the pair would permanently bar anyone who
            # was ever denied from asking again, and deleting denied rows
            # to work around that would erase the decision history.
            models.UniqueConstraint(
                fields=["requester", "pi_group"],
                condition=models.Q(status="pending"),
                name="unique_pending_join_request",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.requester.username} -> {self.pi_group.group.name} "
            f"({self.status})"
        )
