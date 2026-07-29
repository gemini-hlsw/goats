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

    Targets saved before this model existed have no row here; the
    dashboard shows those as saved but with unknown attribution rather
    than guessing.

    Attributes
    ----------
    locus_id : `models.CharField`
        The ANTARES locus ID that was saved. Unique -- re-saving the same
        locus updates the existing row rather than accumulating rows.
    saved_by : `models.ForeignKey`
        The user who saved it. `SET_NULL` on delete so removing a user
        account doesn't delete the save record, it just loses the
        attribution (displayed as unknown rather than vanishing).
    saved_at : `models.DateTimeField`
        When the save happened.

    """

    locus_id = models.CharField(max_length=64, unique=True, db_index=True)
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="antares_target_saves",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        who = self.saved_by.username if self.saved_by else "unknown"
        return f"{self.locus_id} saved by {who}"
