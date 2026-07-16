"""Shared logic for saving an ANTARES locus as a GOATS `Target`.

Used by:
- `goats_tom.tasks.ingest_antares_stream`, when the "Automatically save
  all ingested loci as targets" option is enabled on the subscription.
- `goats_tom.views.antares_locus_dashboard.antares_locus_save_targets`,
  the dashboard's "Save selected" button.

The antares2goats browser extension (see
`goats_tom.api_views.antares2goats.Antares2GoatsViewSet`) saves targets via
a separate path directly from the ANTARES portal, but produces targets in
the same shape (`Target.name == locus_id` via `ANTARESBroker.to_target`,
plus light curve data via `process_lightcurve_data`/`create_lightcurve_dp`/
`create_reduced_datums`) -- `save_locus_as_target` here follows the exact
same sequence, so targets saved through GOATS' own two paths match
extension-saved ones, and `locus_is_saved_as_target` correctly recognizes
extension-saved targets too.
"""

__all__ = ["locus_is_saved_as_target", "save_locus_as_target", "SaveLocusError"]

import logging

from tom_alerts.alerts import get_service_class as tom_alerts_get_service_class
from tom_targets.models import Target

logger = logging.getLogger(__name__)


class SaveLocusError(Exception):
    """Raised when a locus cannot be fetched or saved as a target."""


def locus_is_saved_as_target(locus_id: str) -> bool:
    """Check whether a locus has already been saved as a `Target`.

    Checks both `Target.name` and each target's `TargetName` aliases
    (via `Target.names`, TOM Toolkit's own name+alias union) rather than
    just `Target.name` -- a locus could in principle be recorded as an
    alias on a target that was saved or renamed some other way, outside
    the paths this module controls, and we don't want to let someone
    create a duplicate target in that case.

    Parameters
    ----------
    locus_id : str
        ANTARES locus ID to check.

    Returns
    -------
    bool
        Whether any existing `Target` has this locus_id as its name or as
        one of its aliases.
    """
    # `Target.names` is a Python-level property (name + aliases), not a
    # queryable field, so we check the two underlying sources directly at
    # the database level rather than loading every target into Python.
    if Target.objects.filter(name=locus_id).exists():
        return True
    return Target.objects.filter(aliases__name=locus_id).exists()


def save_locus_as_target(locus_id: str) -> Target:
    """Fetch a locus from ANTARES and save it as a GOATS `Target`, including
    its light curve.

    Mirrors what `Antares2GoatsViewSet.perform_create` does for the
    browser-extension save path -- target creation plus light curve
    ingestion -- so all three save paths (extension, the subscription's
    auto-save option, and the dashboard's manual save) produce targets in
    the same shape.

    Parameters
    ----------
    locus_id : str
        ANTARES locus ID to fetch and save.

    Returns
    -------
    `Target`
        The newly created target. Returned even if light curve ingestion
        fails after target creation -- that failure is logged, not raised
        (see notes below).

    Raises
    ------
    SaveLocusError
        If the locus can't be fetched from ANTARES, or if the target
        itself fails to save, for a reason other than the target already
        existing (that case is handled by checking
        `locus_is_saved_as_target` first, not by catching the resulting
        `IntegrityError` here). Does NOT raise if only light curve
        ingestion fails after the target was already saved successfully.
    """
    broker = tom_alerts_get_service_class("ANTARES")()

    alert = next(broker.fetch_alerts({"locusid": locus_id}), None)
    if alert is None:
        raise SaveLocusError(f"No ANTARES alert data found for locus {locus_id!r}.")

    try:
        target, extras, aliases = broker.to_target(alert)
        target.save(extras=extras, names=aliases)
    except Exception as exc:
        raise SaveLocusError(
            f"Failed to save locus {locus_id!r} as a target: {exc}"
        ) from exc

    # Matches the browser extension's save path (see
    # Antares2GoatsViewSet.perform_create) so targets saved from GOATS
    # itself get the same light curve data extension-saved targets do.
    # Kept as a separate try/except from the target save above: a light
    # curve failure shouldn't discard an already-created target, just be
    # logged as a partial success.
    try:
        lightcurve_data = broker.process_lightcurve_data(alert=alert)
        dp = broker.create_lightcurve_dp(target, lightcurve_data)
        broker.create_reduced_datums(dp)
    except Exception:
        logger.exception(
            "Saved target id=%s for locus %s, but failed to ingest its "
            "light curve.",
            target.pk,
            locus_id,
        )

    logger.info("Saved ANTARES locus %s as target id=%s.", locus_id, target.pk)
    return target
