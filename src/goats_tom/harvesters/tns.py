"""Module that creates a harvester using the TNSClient."""

__all__ = ["TNSHarvester"]
import requests
from astropy import units as u
from astropy.coordinates import SkyCoord
from tom_catalogs.harvester import AbstractHarvester
from tom_targets.models import BaseTarget

from goats_tom.tns import TNSClient


class TNSHarvester(AbstractHarvester):
    """A harvester for querying the TNS catalog and converting results into targets."""

    name = "TNS"
    help_text = "Requires object name without prefix."

    def __init__(self) -> None:
        self.client = TNSClient()

    def query(self, term: str) -> None:
        """Queries the TNS catalog for a specific object.

        Parameters
        ----------
        term : `str`
            The search term, typically the object name without a prefix.
        """
        try:
            self.catalog_data = self.client.get_object(term)
        except requests.HTTPError:
            # Setting this allows the proper UI error to display.
            self.catalog_data = {}

    def to_target(self) -> BaseTarget:
        """Converts the catalog data into a target object.

        Returns
        -------
        `BaseTarget`
            The target object populated with data from the TNS catalog.
        """
        target = super().to_target()
        target.type = "SIDEREAL"
        target.name = self.catalog_data["name"]
        c = SkyCoord(
            f"{self.catalog_data['right_ascension']} "
            f"{self.catalog_data['declination']}",
            unit=(u.hourangle, u.deg),
        )
        target.ra, target.dec = c.ra.deg, c.dec.deg
        return target
