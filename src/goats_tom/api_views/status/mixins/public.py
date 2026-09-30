"""
Status views for services checked without signing in.
"""

__all__ = [
    "ALeRCEPublicStatusMixin",
    "ANTARESPublicStatusMixin",
    "GaiaPublicStatusMixin",
    "HorizonsPublicStatusMixin",
    "NEDPublicStatusMixin",
    "PublicStatusMixin",
    "ScoutPublicStatusMixin",
    "SIMBADPublicStatusMixin",
]

from urllib.parse import urljoin

from astroquery.ipac.ned import conf as ned_conf
from astroquery.jplhorizons import conf as horizons_conf
from astroquery.simbad import conf as simbad_conf
from rest_framework.request import Request
from tom_alerts.brokers import alerce, gaia, scout

from goats_tom.antares_client.config import ANTARESConfig
from goats_tom.service_checks import CheckResult

from .base import BaseStatusMixin, register_status


class PublicStatusMixin(BaseStatusMixin):
    """Checks that a service's server answers, for services GOATS uses without
    credentials."""

    uses_credentials = False

    def get_credentials(self, request: Request) -> dict:
        """
        Returns no credentials; the check is made without signing in.

        Parameters
        ----------
        request : Request
            The incoming HTTP request.

        Returns
        -------
        dict
            An empty dictionary.
        """
        return {}

    def check_service(self, credentials: dict, *args, **kwargs) -> CheckResult:
        """
        Checks that the service's server answers.

        Parameters
        ----------
        credentials : dict
            Unused.

        Returns
        -------
        CheckResult
            The outcome of the check.
        """
        return self.check_public()


@register_status("alerce", "ALeRCE Alert Broker", url=alerce.ALERCE_URL)
class ALeRCEPublicStatusMixin(PublicStatusMixin):
    service_name = "ALeRCE"

    def get_public_url(self) -> str:
        return alerce.ALERCE_SEARCH_URL


@register_status(
    "antares",
    "ANTARES Alert Broker",
    url="https://antares.noirlab.edu",
)
class ANTARESPublicStatusMixin(PublicStatusMixin):
    service_name = "ANTARES"

    def get_public_url(self) -> str:
        """
        Returns the ANTARES loci search, for the configured environment.

        Returns
        -------
        str
            The URL to request; the API's root answers 404.
        """
        return f"{urljoin(ANTARESConfig.get_api_url(), 'loci')}?page[limit]=1"


@register_status("gaia", "Gaia Alerts", url=f"{gaia.BASE_BROKER_URL}/alerts/")
class GaiaPublicStatusMixin(PublicStatusMixin):
    service_name = "Gaia Alerts"

    def get_public_url(self) -> str:
        # The index the broker reads; the site's root answers 403.
        return f"{gaia.BASE_BROKER_URL}/alerts/alertsindex"


@register_status("horizons", "JPL Horizons", url="https://ssd.jpl.nasa.gov/horizons/")
class HorizonsPublicStatusMixin(PublicStatusMixin):
    service_name = "JPL Horizons"

    def get_public_url(self) -> str:
        return horizons_conf.horizons_server


@register_status("scout", "JPL Scout", url="https://cneos.jpl.nasa.gov/scout/")
class ScoutPublicStatusMixin(PublicStatusMixin):
    service_name = "JPL Scout"

    def get_public_url(self) -> str:
        return scout.SCOUT_URL


@register_status(
    "ned",
    "NASA/IPAC Extragalactic Database (NED)",
    url="https://ned.ipac.caltech.edu/",
)
class NEDPublicStatusMixin(PublicStatusMixin):
    service_name = "NED"

    def get_public_url(self) -> str:
        # The server astroquery queries; its cgi-bin/ root answers 403.
        return urljoin(ned_conf.server, "/")


@register_status("simbad", "SIMBAD")
class SIMBADPublicStatusMixin(PublicStatusMixin):
    service_name = "SIMBAD"

    def get_public_url(self) -> str:
        return f"https://{simbad_conf.server}/simbad/"
