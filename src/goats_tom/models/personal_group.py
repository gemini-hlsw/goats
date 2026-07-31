"""Module for `PersonalGroup` model."""

__all__ = ["PersonalGroup"]

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class PersonalGroup(models.Model):
    """Links a user to the private group representing "just me".

    Every user gets one (see `goats_tom.signals.ensure_user_has_a_group`),
    because GOATS runs with ``TARGET_PERMISSIONS_ONLY = False``: observation
    records, data products and reduced datums are permissioned per *group*
    rather than inheriting visibility from their target. TOM populates the
    observation form's group selector from the user's own groups and leaves
    the field optional, and ships no default group -- so a user belonging to
    no group can create an observation record permissioned to nobody,
    invisible to everyone but superusers. A personal group guarantees there
    is always something to select, and selecting it means "visible to me
    alone".

    Exists as a model rather than being inferred from the group's *name*
    (e.g. ``user-<username>``) for two reasons, both of which caused real
    bugs:

    - Reusing a user's existing group has to be decided by ownership. Keying
      on the name meant that when a membership was lost, the next save found
      the name taken and created ``user-<username>-2`` instead of reusing the
      original -- leaving one empty group and one real one.
    - Filtering personal groups out of the group pickers has to be exact.
      Matching a ``user-`` name prefix would also hide any legitimate group
      somebody happened to name that way.

    Mirrors `goats_tom.models.AntaresPIGroup`, which links a group to its PI
    for the same reasons.

    Attributes
    ----------
    user : `models.OneToOneField`
        The user this group belongs to. `CASCADE`: a personal group with no
        person has nothing to represent.
    group : `models.OneToOneField`
        The underlying auth group. `CASCADE` for the same reason.
    created_at : `models.DateTimeField`
        When the group was created.

    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_group",
    )
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="personal_group",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "personal group"
        verbose_name_plural = "personal groups"

    def __str__(self) -> str:
        return f"{self.group.name} (personal group for {self.user.username})"
