"""Module for `AntaresDashboardMembership` model."""

__all__ = ["AntaresDashboardMembership"]

from django.conf import settings
from django.db import models


class AntaresDashboardMembership(models.Model):
    """What a non-PI member is allowed to do on a PI's ANTARES dashboard.

    Two permissions, held per (group, user) pair: view the dashboard, and
    save loci from it as GOATS targets. A member may hold either, both, or
    -- transiently, if a PI revokes both without removing the row --
    neither.

    Deliberately an explicit table rather than django-guardian object
    permissions on the subscription. Guardian is what the rest of TOM uses
    and would have been the more idiomatic choice, but with exactly two
    flags it buys indirection and costs legibility: a PI's management page
    needs to render "who has access, and to what" as a simple table, and
    an auditor needs to answer "what can this user do" without decoding
    permission strings. If the permission set grows much beyond these two,
    revisiting guardian is the right call.

    Note that a PI is *not* represented here. Their access follows from
    owning the subscription (see
    `goats_tom.models.AntaresStreamSubscription.owner`), so it can never be
    accidentally revoked by deleting a membership row, and there is no way
    for the two sources to disagree about what the owner may do.

    Attributes
    ----------
    pi_group : `models.ForeignKey`
        The PI group this membership is within -- i.e. whose dashboard is
        being shared. `CASCADE`: memberships are meaningless without the
        group.
    user : `models.ForeignKey`
        The member. `CASCADE`: a deleted account's access should disappear
        with it, not linger as a row granting permissions to a primary key
        that may later be reused.
    can_view_dashboard : `models.BooleanField`
        Whether this member may view the PI's locus dashboard.
    can_save_targets : `models.BooleanField`
        Whether this member may save loci from that dashboard as GOATS
        targets. Defaults to `False`: saving creates `Target` rows and
        fetches light curves, so it is the more consequential of the two
        and is opt-in rather than implied by viewing.
    granted_by : `models.ForeignKey`
        Who approved this access -- normally the PI. `SET_NULL` so
        deleting that account loses the attribution rather than the
        membership itself, which the member is presumably still using.
    granted_at : `models.DateTimeField`
        When access was granted.
    updated_at : `models.DateTimeField`
        When the permissions were last changed, so a PI can see whether a
        grant is current or long-standing.

    """

    pi_group = models.ForeignKey(
        "goats_tom.AntaresPIGroup",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="antares_dashboard_memberships",
    )
    can_view_dashboard = models.BooleanField(default=True)
    can_save_targets = models.BooleanField(default=False)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antares_memberships_granted",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ANTARES dashboard membership"
        verbose_name_plural = "ANTARES dashboard memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["pi_group", "user"],
                name="unique_membership_per_group_and_user",
            )
        ]

    def __str__(self) -> str:
        granted = [
            name
            for name, held in (
                ("view", self.can_view_dashboard),
                ("save", self.can_save_targets),
            )
            if held
        ]
        return (
            f"{self.user.username} in {self.pi_group.group.name}: "
            f"{', '.join(granted) if granted else 'no permissions'}"
        )
