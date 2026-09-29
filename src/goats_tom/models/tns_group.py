"""Module for `TNSGroup` model."""

__all__ = ["TNSGroup"]

from django.conf import settings
from django.db import models


class TNSGroup(models.Model):
    """One TNS group that a credential owner's bot can post to.

    These rows are the record of which groups a bot may file under. The
    names were a list of strings on `goats_tom.models.TNSLogin`, which made
    the text the identity of a group: renaming one revoked every member
    approved for the old spelling. A membership points at a row, so a rename
    is an edit it survives.

    Attributes
    ----------
    owner : `models.ForeignKey`
        The user whose TNS bot credentials post to this group.
    name : `models.CharField`
        The TNS group name, spelled exactly as it is on TNS.
    allow_join_requests : `models.BooleanField`
        Whether other users may ask for access. Defaults to `False`, so
        upgrading GOATS never exposes an existing user's groups.
    recommended_authors : `models.TextField`
        Author list to pre-fill on posts made through this group. Blank
        falls back to `tom_tns`'s own default.
    created_at : `models.DateTimeField`
        When the group was first recorded.
    updated_at : `models.DateTimeField`
        When its settings were last changed.
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
            # Two rows for one real group would split its settings in two.
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
            `True` if the owner has a `TNSLogin`. Deleting credentials
            leaves these rows behind, so a group can outlive them and
            callers must check before offering it for posting.
        """
        return hasattr(self.owner, "tnslogin")
