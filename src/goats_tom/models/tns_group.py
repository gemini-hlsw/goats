"""Module for `TNSGroup` model."""

__all__ = ["TNSGroup"]

from django.conf import settings
from django.db import models


class TNSGroup(models.Model):
    """One TNS group that a credential owner's bot can post to.

    `goats_tom.models.TNSLogin.group_names` already holds the same names as
    a `JSONField`, and that field is deliberately left in place -- it is
    what `goats_tom.middleware.tns` reads to build the payload for a user
    posting under their own credentials, and rewriting that path would
    change behaviour that works today for no gain.

    This table exists because the JSON list cannot carry anything *about* a
    group. Sharing is per-group (an owner may be happy for colleagues to
    post as one collaboration but not another), the recommended author list
    is per-group (different collaborations have different author lists), and
    a join request has to point at something with a primary key. A list of
    strings supports none of that.

    Rows are kept in step with `TNSLogin.group_names` by
    `goats_tom.tns_membership.sync_groups_for_login`, called whenever
    credentials are saved. The JSON list stays the source of truth for
    *which* groups exist; this table holds the settings hanging off them.

    Attributes
    ----------
    owner : `models.ForeignKey`
        The user whose TNS bot credentials post to this group. `CASCADE`:
        without the owner there are no credentials, so the group is not
        postable by anyone and its memberships mean nothing.
    name : `models.CharField`
        The TNS group name, exactly as it is spelled on TNS. Must match,
        since `tom_tns.forms` looks the name up against TNS's own group
        list (`get_reverse_tns_values('groups', name)`) and silently drops
        anything it cannot resolve.
    allow_join_requests : `models.BooleanField`
        The owner's opt-in toggle. When `False` the group is invisible to
        everyone else -- it is not offered for request and does not appear
        in any listing. Defaults to `False` so that upgrading GOATS never
        silently exposes an existing user's groups: sharing a bot means
        posts go out under the owner's name, so it has to be a decision
        somebody made rather than a default they inherited.
    recommended_authors : `models.TextField`
        Names to pre-fill into the Reporter / Classifier field of any post
        made through this group. Free text, because that is exactly what
        TNS takes -- a single author-list string. Blank means the form
        falls back to `tom_tns`'s own default (the submitting user's name).
    created_at : `models.DateTimeField`
        When the group was first recorded.
    updated_at : `models.DateTimeField`
        When its settings were last changed, so an owner can tell whether
        the author list is current.

    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tns_groups",
    )
    name = models.CharField(max_length=100)
    allow_join_requests = models.BooleanField(default=False)
    recommended_authors = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TNS group"
        verbose_name_plural = "TNS groups"
        ordering = ["name"]
        constraints = [
            # Two rows for the same (owner, name) would split a single real
            # TNS group's settings in two, and the sync helper would have no
            # way to decide which one it is updating.
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_tns_group_per_owner",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} (bot owner: {self.owner.username})"

    @property
    def has_credentials(self) -> bool:
        """Whether the owner still has TNS credentials stored.

        Returns
        -------
        bool
            `True` if the owner has a `TNSLogin`.

        Notes
        -----
        Deleting credentials does not delete these rows -- an owner who
        rotates a bot key would otherwise lose every sharing setting and
        every membership they had granted. So a group can outlive the
        credentials it describes, and anything that offers a group for
        posting has to check this first rather than assume.
        """
        return hasattr(self.owner, "tnslogin")
