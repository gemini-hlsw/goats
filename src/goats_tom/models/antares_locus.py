"""Module for `AntaresLocus` model."""

__all__ = ["AntaresLocus"]

from django.db import models


class AntaresLocus(models.Model):
    """Staging row summarizing the live state of an ANTARES locus.

    One row per ``locus_id``, updated in place as new alerts arrive on the
    ANTARES Kafka alert stream (see ``goats_tom.tasks.ingest_antares_stream``).
    Rows are purged after 1 day of inactivity by the periodic
    ``cleanup_stale_antares_loci`` task.

    Attributes
    ----------
    locus_id : `models.CharField`
        ANTARES ID for the locus. Unique per row.
    ra : `models.FloatField`
        Right ascension of the locus centroid, in degrees. Converted to
        sexagesimal for display at render time rather than stored
        separately, to avoid a redundant derived copy drifting from this
        source value.
    dec : `models.FloatField`
        Declination of the locus centroid, in degrees. See `ra` re:
        sexagesimal display.
    latest_alert_id : `models.CharField`
        ANTARES ID of the most recently seen alert for this locus.
    latest_alert_mjd : `models.FloatField`
        Modified Julian Date of the most recently seen alert, if known.
    latest_alert_magnitude : `models.FloatField`
        Magnitude of the most recently seen alert, from ANTARES
        ``properties["newest_alert_magnitude"]``, if known.
    latest_alert_topic : `models.CharField`
        The ANTARES Kafka topic the most recent alert for this locus
        arrived on, with ANTARES's internal "client." prefix stripped so
        it matches the topic names shown/selected on the ingestion page.
        A locus can appear on more than one subscribed topic; this
        records whichever one delivered the latest alert, not all of
        them. Indexed, since the dashboard allows sorting by it.
    in_tns : `models.BooleanField`
        Whether this locus is cross-matched to a TNS (Transient Name
        Server) public object, from ``"tns_public_objects" in
        locus.catalogs``.
    first_seen : `models.DateTimeField`
        When this locus first appeared in the staging table.
    last_updated : `models.DateTimeField`
        When this locus was last touched by a new alert. Used to determine
        the 1-day expiry window.

    """

    locus_id = models.CharField(max_length=64, unique=True, db_index=True)
    ra = models.FloatField()
    dec = models.FloatField()
    latest_alert_id = models.CharField(max_length=128)
    latest_alert_mjd = models.FloatField(null=True, blank=True)
    latest_alert_magnitude = models.FloatField(null=True, blank=True)
    latest_alert_topic = models.CharField(
        max_length=256, blank=True, default="", db_index=True
    )
    in_tns = models.BooleanField(default=False)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-last_updated"]
        verbose_name_plural = "ANTARES loci"

    def __str__(self) -> str:
        return self.locus_id
