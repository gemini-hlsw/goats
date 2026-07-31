"""Module for `AntaresTargetSave` model."""

__all__ = ["AntaresTargetSave"]

from django.conf import settings
from django.db import models


class AntaresTargetSave(models.Model):
    """Records which user saved a given ANTARES locus as a GOATS `Target`.

    TOM Toolkit's `Target` has no "created by" field of its own (only a
    `created` timestamp and guardian-backed `permissions`), so there is
    otherwise no way to tell who saved a target -- and for targets left
    PUBLIC, guardian permissions don't narrow it down either. This is a
    small side-table recording that attribution explicitly.

    Keyed on `locus_id` rather than a `Target` foreign key so the record
    survives the dashboard being cleared and re-populated, and so it can
    be looked up with the same locus IDs the dashboard already works in
    (see `goats_tom.views.antares_locus_dashboard._saved_locus_ids`). A
    consequence is that deleting a target outside this module leaves a
    row here pointing at a locus that is no longer saved -- harmless,
    since the dashboard only ever shows attribution for loci it has
    independently confirmed are currently saved, so a stale row is never
    displayed.

    There may be several rows per locus, one per user who saved it. A
    locus is one real object in the sky and GOATS keeps exactly one
    `Target` for it (`Target.name` is unique, and TOM additionally
    rejects fuzzy and alias collisions), so two teams interested in the
    same locus share that one target rather than each getting their own
    copy. Saving an already-saved locus therefore grants the second team
    access instead of failing, and each such save is recorded here --
    which is why `locus_id` is no longer unique on its own.

    Targets saved before this model existed have no row here; the
    dashboard shows those as saved but with unknown attribution rather
    than guessing.

    Attributes
    ----------
    locus_id : `models.CharField`
        The ANTARES locus ID that was saved. Unique per saving user, not
        globally -- see the class docstring.
    saved_by : `models.ForeignKey`
        The user who saved it. `SET_NULL` on delete so removing a user
        account doesn't delete the save record, it just loses the
        attribution (displayed as unknown rather than vanishing).
    saved_at : `models.DateTimeField`
        When the save happened. Ordered on, so the earliest row identifies
        the team that created the target and therefore holds change and
        delete permissions on it (see
        `goats_tom.antares_target_save.save_locus_as_target`).

    """

    locus_id = models.CharField(max_length=64, db_index=True)
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antares_target_saves",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ANTARES target save"
        verbose_name_plural = "ANTARES target saves"
        ordering = ["saved_at"]
        constraints = [
            # One row per (locus, user), so re-saving is idempotent for a
            # given user while still allowing a second user -- from a
            # different team -- to record their own save of the same locus.
            models.UniqueConstraint(
                fields=["locus_id", "saved_by"],
                name="unique_target_save_per_locus_and_user",
            )
        ]

    def __str__(self) -> str:
        who = self.saved_by.username if self.saved_by else "unknown"
        return f"{self.locus_id} saved by {who}"
