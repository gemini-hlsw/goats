"""Module for `AntaresPIGroup` model."""

__all__ = ["AntaresPIGroup"]

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class AntaresPIGroup(models.Model):
    """Links a `django.contrib.auth.models.Group` to the PI who owns it.

    Created automatically when a user first stores ANTARES Kafka
    credentials (see
    `goats_tom.views.logins.antares_kafka.AntaresKafkaLoginView`) -- at
    that point they can run their own stream subscription, so they need a
    group other users can ask to join.

    Exists as a model rather than being inferred from the group's *name*
    (e.g. ``antares-<username>``) because two things need to be answered
    cheaply and unambiguously: "who approves join requests for this
    group?" and "which group belongs to this PI?". Parsing a username back
    out of a group name answers neither reliably -- it breaks on a
    username change, on any name collision, and on any group created by
    hand or by another part of GOATS that happens to match the pattern.

    Why a plain auth `Group` at all, rather than only the membership rows
    in `goats_tom.models.AntaresDashboardMembership`: TOM Toolkit's target
    sharing is group-based (`tom_targets.forms` assigns guardian
    view/change/delete permissions to `Group` objects), so a real `Group`
    is what lets a saved target be shared with a PI's whole team. The
    membership table carries the two dashboard-specific permissions that
    have no equivalent in TOM's model; the `Group` carries team identity.

    Attributes
    ----------
    group : `models.OneToOneField`
        The underlying auth group. `CASCADE` on delete: if the group is
        removed, this link has nothing left to describe.
    pi : `models.OneToOneField`
        The principal investigator who owns the group and decides its
        join requests. One group per PI, matching one subscription per PI
        (see `goats_tom.models.AntaresStreamSubscription.owner`).

        `CASCADE` on delete, unlike `owner` on the subscription: a group
        with no PI has nobody who can approve requests or grant access to
        it, so keeping it would leave an unusable group and a queue of
        requests that can never be decided.
    created_at : `models.DateTimeField`
        When the group was created for this PI.

    """

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="antares_pi_group",
    )
    pi = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="antares_pi_group",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ANTARES PI group"
        verbose_name_plural = "ANTARES PI groups"

    def __str__(self) -> str:
        return f"{self.group.name} (PI: {self.pi.username})"
