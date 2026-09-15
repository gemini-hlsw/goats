"""Module for `TNSGroupMembership` model."""

__all__ = ["TNSGroupMembership"]

from django.conf import settings
from django.db import models


class TNSGroupMembership(models.Model):
    """Permission to post to TNS through one owner's bot, for one group.

    A single permission, so there are no flags here --  holding a row *is*
    the permission. This is narrower than
    `goats_tom.models.AntaresDashboardMembership`, which carries two, and
    the difference is deliberate: reporting and classifying are the same
    act as far as TNS credentials are concerned, and splitting them would
    imply a distinction the TNS API does not make.

    Unlike the ANTARES equivalent, this grants **no** access to any target
    and does not add the member to any `django.contrib.auth.models.Group`.
    Target visibility is decided entirely separately, by TOM Toolkit's own
    sharing; a member can only reach the TNS page for a target they could
    already open. Conflating the two would mean approving a TNS request
    silently handed over data.

    The owner is not represented here. Their ability to post follows from
    owning the credentials, so it cannot be accidentally revoked by
    deleting a row and the two can never disagree.

    Attributes
    ----------
    tns_group : `models.ForeignKey`
        The group being shared. `CASCADE`: without it there is nothing to
        post to.
    user : `models.ForeignKey`
        The member. `CASCADE`, so a deleted account's permission goes with
        it rather than lingering against a primary key that may be reused.
    granted_by : `models.ForeignKey`
        Who approved it -- normally the owner. `SET_NULL` so deleting that
        account loses the attribution, not the access the member is
        presumably still using.
    granted_at : `models.DateTimeField`
        When access was granted.
    updated_at : `models.DateTimeField`
        When the row was last touched.

    """

    tns_group = models.ForeignKey(
        "goats_tom.TNSGroup",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tns_group_memberships",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tns_memberships_granted",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TNS group membership"
        verbose_name_plural = "TNS group memberships"
        ordering = ["user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["tns_group", "user"],
                name="unique_tns_membership_per_group_and_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} may post as {self.tns_group.name}"
