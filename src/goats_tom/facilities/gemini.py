"""Gemini facility."""

__all__ = ["GEMObservationForm", "GOATSGEMFacility"]

import logging
from typing import Any
from datetime import datetime, timezone

import requests
from astropy import units as u
from django.http import HttpRequest
from tom_dataproducts.models import DataProduct
from tom_observations.facility import (
    BaseRoboticObservationFacility,
    BaseRoboticObservationForm,
)
from django import forms
from tom_observations.models import ObservationRecord
from gpp_client.api.enums import ObservingModeType
from goats_tom.astroquery import Observations as GOA
from goats_tom.ocs import OCSClient
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


TERMINAL_OBSERVING_STATES = ["TRIGGERED", "ON_HOLD"]

# Units of flux and wavelength for converting to Specutils Spectrum1D objects
FLUX_CONSTANT = (1 * u.erg) / (u.cm**2 * u.second * u.angstrom)
WAVELENGTH_UNITS = u.angstrom

SITES = {
    "Cerro Pachon": {
        "sitecode": "cpo",
        "latitude": -30.24075,
        "longitude": -70.736694,
        "elevation": 2722.0,
    },
    "Maunakea": {
        "sitecode": "mko",
        "latitude": 19.8238,
        "longitude": -155.46905,
        "elevation": 4213.0,
    },
}

ocs_client = OCSClient()

class GEMObservationForm(BaseRoboticObservationForm):
    gpp_id = forms.CharField(required=True)
    observation_id = forms.CharField(required=True)
    instrument = forms.CharField(required=False)
    title = forms.CharField(required=False)
    image_quality = forms.CharField(required=False)
    cloud_extinction = forms.CharField(required=False)
    sky_background = forms.CharField(required=False)
    water_vapor = forms.CharField(required=False)

    # All FIELD_MAP keys are relative to `observing_parameters`, which is passed
    # directly as the `data` dict to this form. So do NOT prefix paths with
    # "observing_parameters."
    BASE_FIELD_MAP = {
        "gpp_id": "id",
        "observation_id": "reference.label",
        "instrument": "instrument",
        "title": "title",
        "image_quality": "constraintSet.imageQuality",
        "cloud_extinction": "constraintSet.cloudExtinction",
        "sky_background": "constraintSet.skyBackground",
        "water_vapor": "constraintSet.waterVapor",
        "target_id": "target_id",
        "facility": "facility",
    }

    FIELD_MAP = {}

    def __init__(self, data=None, *args, **kwargs):
        if isinstance(data, dict):
            combined_map = {**self.BASE_FIELD_MAP, **self.FIELD_MAP}
            data = self.map_flat_fields(data, combined_map)
        super().__init__(data=data, *args, **kwargs)

    @staticmethod
    def extract_value(data: dict, path: str):
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    @classmethod
    def map_flat_fields(cls, source: dict, field_map: dict) -> dict:
        return {
            flat_key: cls.extract_value(source, dotted_path)
            for flat_key, dotted_path in field_map.items()
        }

    def clean_observation_id(self):
        observation_id = self.cleaned_data.get("observation_id")
        if ObservationRecord.objects.filter(observation_id=observation_id).exists():
            raise forms.ValidationError(f"An observation with ID '{observation_id}' already exists.")
        return observation_id


class GMOSSouthForm(GEMObservationForm):
    grating = forms.CharField(required=False)
    filter = forms.CharField(required=False)

    FIELD_MAP = {
        "grating": "observingMode.gmosSouthLongSlit.grating",
        "filter": "observingMode.gmosSouthLongSlit.filter"
    }


class GMOSNorthForm(GEMObservationForm):
    grating = forms.CharField(required=False)
    filter = forms.CharField(required=False)

    FIELD_MAP = {
        "grating": "observingMode.gmosNorthLongSlit.grating",
        "filter": "observingMode.gmosNorthLongSlit.filter",
    }


class GOATSGEMFacility(BaseRoboticObservationFacility):
    """The ``GEMFacility`` is the interface to the Gemini Telescope. For
    information regarding Gemini observing and the available parameters, please
    see https://www.gemini.edu/observing/start-here
    """

    name = "GEM"
    observation_forms = {
        ObservingModeType.GMOS_SOUTH_LONG_SLIT.value: GMOSSouthForm,
        ObservingModeType.GMOS_NORTH_LONG_SLIT.value: GMOSNorthForm
    }

    def get_form(self, observation_type):
        """Return the appropriate form to use."""
        return self.observation_forms.get(observation_type, GEMObservationForm)

    def submit_observation(self, observation_payload: list[dict[str, Any]]):
        # TODO: Need to return observation ids as a list.
        print("Submitting observations to Gemini is not supported yet.")
        return [observation_payload["params"]["observation_id"]]

    def validate_observation(self, observation_payload: dict) -> dict:
        """Validates the observation payload.

        Parameters
        ----------
        observation_payload : `dict`
            The observation payload.

        Returns
        -------
        `dict`
            Errors, if any.

        """
        # Gemini doesn't have an API for validation, but run some checks.
        errors = {}
        if "elevationType" in observation_payload[0].keys():
            if observation_payload[0]["elevationType"] == "airmass":
                if float(observation_payload[0]["elevationMin"]) < 1.0:
                    errors["elevationMin"] = "Airmass must be >= 1.0"
                if float(observation_payload[0]["elevationMax"]) > 2.5:
                    errors["elevationMax"] = "Airmass must be <= 2.5"

        for payload in observation_payload:
            if "error" in payload.keys():
                errors["exptimes"] = payload["error"]
            if "exptime" in payload.keys():
                if payload["exptime"] <= 0:
                    errors["exptimes"] = "Exposure time must be >= 1"
                if payload["exptime"] > 1200:
                    errors["exptimes"] = "Exposure time must be <= 1200"

        return errors

    def get_observation_url(self, observation_id):
        return GOA.get_search_url(observation_id)

    def get_start_end_keywords(self):
        return ("window_start", "window_end")

    def get_terminal_observing_states(self):
        return TERMINAL_OBSERVING_STATES

    def get_observing_sites(self):
        return SITES

    def get_observation_status(self, observation_id):
        try:
            observation_summary = ocs_client.get_observation_summary(observation_id)

            if not observation_summary["success"]:
                raise Exception(f"{observation_summary['error']}")

            state = observation_summary["data"]["status"]

        except Exception as e:
            logger.error(e)
            state = "Error"
        return {"state": state, "scheduled_start": None, "scheduled_end": None}

    def get_flux_constant(self) -> u:
        """Returns the astropy quantity that a facility uses for its spectral flux
        conversion.
        """
        return FLUX_CONSTANT

    def get_wavelength_units(self):
        """Returns the astropy units that a facility uses for its spectral
        wavelengths
        """
        return WAVELENGTH_UNITS

    def is_fits_facility(self, header):
        """Returns True if the FITS header is from this facility based on valid
        keywords and associated
        values, False otherwise.
        """
        telescope = header.get("TELESCOP", "")
        return "gemini" in telescope.lower()

    def get_facility_weather_urls(self):
        """Returns a dictionary containing a URL for weather information
        for each site in the Facility SITES. This is intended to be useful
        in observation planning.

        `facility_weather = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'weather_url': 'http://path/to/weather'}`

        """
        sites_status = [
            {"code": "cpo", "weather_url": "https://www.gemini.edu/sciops/schedules/obsStatus/GS_Instrument.html"},
            {"code": "mko", "weather_url": "https://www.gemini.edu/sciops/schedules/obsStatus/GN_Instrument.html"}
        ]
        status = {"code": self.name, "sites": sites_status}
        return status

    def get_facility_status(self):
        """Returns a dictionary describing the current availability of the
        Facility
        telescopes. This is intended to be useful in observation planning.
        The top-level (Facility) dictionary has a list of sites. Each site
        is represented by a site dictionary which has a list of telescopes.
        Each telescope has an identifier (code) and an status string.

        The dictionary hierarchy is of the form:

        `facility_dict = {'code': 'XYZ', 'sites': [ site_dict, ... ]}`
        where
        `site_dict = {'code': 'XYZ', 'telescopes': [ telescope_dict, ... ]}`
        where
        `telescope_dict = {'code': 'XYZ', 'status': 'AVAILABILITY'}`

        See lco.py for a concrete implementation example.
        """
        def fetch_shutter_from_json(url: str, timeout: int = 5) -> str:
            """Fetch 'open' status from the Gemini South JSON endpoint."""
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                status = data.get("open")
                if status is not None:
                    return status.strip('"')
                return "NO STATUS FOUND"
            except Exception:
                return "ERROR FETCHING STATUS"

        def fetch_shutter_from_html(url: str, timeout: int = 5) -> str:
            """Fetch the 'shutter' status from a Gemini North schedule page."""
            try:
                with requests.get(url, timeout=timeout) as resp:
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    td = soup.find("td", id="shutter")
                    return td.get_text(strip=True) if td else "NO STATUS FOUND"
            except Exception:
                return "ERROR FETCHING STATUS"

        north_url = "https://www.gemini.edu/sciops/schedules/obsStatus/GN_Instrument.html"
        south_url = "https://www.gemini.edu/sciops/schedules/obsStatus/too_GS.json"
        cpo_telescope_status = [
            {"code": "Gemini South", "status": fetch_shutter_from_json(south_url)}
        ]
        mko_telescope_status = [
            {"code": "Gemini North", "status": fetch_shutter_from_html(north_url)}
        ]
        sites_status = [
            {"code": "cpo", "telescopes": cpo_telescope_status},
            {"code": "mko", "telescopes": mko_telescope_status}
        ]
        status = {"code": self.name, "sites": sites_status}
        return status

    def cancel_observation(self, observation_id):
        """Takes an observation id and submits a request to the observatory that
        the observation be cancelled.

        If the cancellation was successful, return True. Otherwise, return
        False.
        """
        raise NotImplementedError(
            "This facility has not implemented cancel observation.",
        )

    def get_date_obs_from_fits_header(self, header: Any) -> str:
        """
        Extract the observation datetime from a FITS header. Combines the ``DATE-OBS``
        and ``TIME-OBS`` fields if both are present. If only ``DATE-OBS`` is provided,
        returns the date alone. If ``DATE-OBS`` is missing, returns the current UTC
        date and time and logs a warning.

        Parameters
        ----------
        header : Any
            FITS header dictionary containing metadata.

        Returns
        -------
        str
            - ``"YYYY-MM-DD HH:MM:SS"`` if both date and time are present.
            - ``"YYYY-MM-DD"`` if only the date is present.
            - Current UTC datetime (``"YYYY-MM-DD HH:MM:SS"``) if no date is available.
        """
        date_obs = header.get("DATE-OBS")
        time_obs = header.get("TIME-OBS")

        if not date_obs:
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            logger.warning(
                "DATE-OBS keyword not found in FITS header. Using current UTC time "
                "instead."
            )
            return now_utc

        return f"{date_obs} {time_obs}" if time_obs else date_obs

    def all_data_products(
        self,
        observation_record: ObservationRecord,
    ) -> dict[str, list[Any]]:
        """Grabs all the data products.

        Parameters
        ----------
        observation_record : `ObservationRecord`
            The observation record to use for querying.

        Returns
        -------
        `dict[str, list[Any]]`
            Saved and unsaved data products.

        """
        products = {"unsaved": []}
        products["saved"] = self.data_products(observation_record)
        return products

    def save_data_products(
        self,
        observation_record: ObservationRecord,
        product_id: str | None = None,
        request: HttpRequest | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> list[DataProduct]:
        raise NotImplementedError(
            "Data products should be downloaded by background task from GOA.",
        )

    def data_products(
        self,
        observation_record: ObservationRecord,
        product_id: str | None = None,
    ) -> list[DataProduct]:
        """Return a list of DataProduct objects for the given observation.

        Parameters
        ----------
        observation_record : `ObservationRecord`
            The observation record to look for data products for.
        product_id : `str | None`, optional
            The product ID to match, by default `None`.

        Returns
        -------
        `list[DataProduct]`
            A list of DataProduct objects.
        """
        products = DataProduct.objects.filter(observation_record=observation_record)
        if product_id is not None:
            products = products.filter(product_id=product_id)
        return list(products)
