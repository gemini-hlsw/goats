"""
Periodic task to purge stale rows from the `AntaresLocus` staging table.
"""

__all__ = ["cleanup_stale_antares_loci"]

import logging

import dramatiq
from django.utils import timezone

from goats_scheduler.scheduling import cron
from goats_tom.models import AntaresLocus

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 1


@cron(hour=0, minute=0)
@dramatiq.actor
def cleanup_stale_antares_loci() -> None:
    """
    Delete `AntaresLocus` rows that have not received a new alert in the
    last `STALE_AFTER_DAYS` days.
    """
    cutoff = timezone.now() - timezone.timedelta(days=STALE_AFTER_DAYS)
    deleted_count, _ = AntaresLocus.objects.filter(last_updated__lt=cutoff).delete()

    if deleted_count:
        logger.info("Purged %d stale ANTARES loci from the staging table.", deleted_count)
