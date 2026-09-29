"""Module for `TNSGroupMembership` model."""

__all__ = ["TNSGroupMembership"]

from django.conf import settings
from django.db import models


class TNSGroupMembership(models.Model):
    """Permission to post to TNS through one owner's bot, for one group.

    Holding a row *is* the permission, so there are no flags. It grants no
    target access and no `django.contrib.auth.models.Group`: visibility is
    decided separately by TOM's own sharing, and a member can only reach
    the TNS page for a target they could already open. The owner is not
    represented here -- their access follows from owning the credentials.

    Attributes
    ----------
    tns_group : `models.ForeignKey`
        The group being shared.
    user : `models.ForeignKey`
        The member.
    granted_by : `models.ForeignKey`
        Who approved it, normally the owner. `SET_NULL`, so deleting that
        account loses the attribution rather than the access.
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
