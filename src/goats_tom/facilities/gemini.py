"""Gemini facility."""

__all__ = ["GEMObservationForm", "GOATSGEMFacility"]

import logging
from typing import Any

import requests
from astropy import units as u
from astropy.time import Time
from crispy_forms.layout import HTML, Div
from dateutil.parser import parse
from django import forms
from django.conf import settings
from django.http import HttpRequest
from requests.exceptions import HTTPError, ReadTimeout
from tom_common.exceptions import ImproperCredentialsException
from tom_dataproducts.models import DataProduct
from tom_observations.facility import (
    BaseRoboticObservationFacility,
    BaseRoboticObservationForm,
    get_service_class,
)
from tom_observations.models import ObservationRecord
from tom_targets.models import Target

from goats_tom.astroquery import Observations as GOA
from goats_tom.ocs import GeminiID, OCSClient
from goats_tom.utils import get_key_info
from requests.exceptions import ConnectTimeout

try:
    AUTO_THUMBNAILS = settings.AUTO_THUMBNAILS
except AttributeError:
    AUTO_THUMBNAILS = False

logger = logging.getLogger(__name__)

try:
    GEM_SETTINGS = settings.FACILITIES["GEM"]
except KeyError:
    GEM_SETTINGS = {
        "portal_url": {
            "GS": "https://gsodb.gemini.edu:8443",
            "GN": "https://gnodb.gemini.edu:8443",
        },
        "api_key": {
            "GS": "",
            "GN": "",
        },
        "user_email": "",
        "programs": {
            "GS-YYYYS-T-NNN": {
                "MM": "Std: Some descriptive text",
                "NN": "Rap: Some descriptive text",
            },
            "GN-YYYYS-T-NNN": {
                "QQ": "Std: Some descriptive text",
                "PP": "Rap: Some descriptive text",
            },
        },
    }

PORTAL_URL = GEM_SETTINGS["portal_url"]
VALID_OBSERVING_STATES = ["TRIGGERED", "ON_HOLD"]
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


def make_request(*args, **kwargs):
    response = requests.request(*args, **kwargs)
    print(response.url)
    if 400 <= response.status_code < 500:
        logger.log(
            msg=f"Gemini request failed: {response.content}", level=logging.WARNING
        )
        raise ImproperCredentialsException("GEM")
    response.raise_for_status()
    return response


def flatten_error_dict(form, error_dict):
    non_field_errors = []
    for k, v in error_dict.items():
        if isinstance(v, list):
            for i in v:
                if isinstance(i, str):
                    if k in form.fields:
                        form.add_error(k, i)
                    else:
                        non_field_errors.append(f"{k}: {i}")
                if isinstance(i, dict):
                    non_field_errors.append(flatten_error_dict(form, i))
        elif isinstance(v, str):
            if k in form.fields:
                form.add_error(k, v)
            else:
                non_field_errors.append(f"{k}: {v}")
        elif isinstance(v, dict):
            non_field_errors.append(flatten_error_dict(form, v))

    return non_field_errors


def proposal_choices():
    choices = []
    for p in GEM_SETTINGS["programs"]:
        choices.append((p, p))
    return choices


def obs_choices():
    choices = []
    for p in GEM_SETTINGS["programs"]:
        for obs in GEM_SETTINGS["programs"][p]:
            obsid = p + "-" + obs
            val = p.split("-")
            showtext = (
                val[0][1]
                + val[1][2:]
                + val[2]
                + val[3]
                + "["
                + obs
                + "] "
                + GEM_SETTINGS["programs"][p][obs]
            )
            choices.append((obsid, showtext))
    return choices


def get_site(progid, location=False):
    values = progid.split("-")
    gemloc = {"GS": "gemini_south", "GN": "gemini_north"}
    site = values[0].upper()
    if location:
        site = gemloc[site]
    return site


class GEMObservationForm(BaseRoboticObservationForm):
    """Defines and collects parameters for the Gemini ToO observation API.

    Refer to https://www.gemini.edu/node/11005 for the ToO process and
    https://www.gemini.edu/node/12109 for user key and authentication.

    Available parameters include prog, email, password, obsnum, target,
    ra, dec, mags, noteTitle, note, posangle, exptime, group, gstarget,
    gsra, gsdec, gsmags, gsprobe, ready, windowDate, windowTime,
    windowDuration, elevationType, elevationMin, elevationMax.

    The server clones a template observation and updates it with the
    provided info. The 'ready' parameter sets the observation status. The
    exposure time is set in the instrument "static component".

    Guide star parameters are optional but recommended. If any gs* parameter
    is specified, gsra, gsdec, and gsprobe must also be specified.

    Errors result in HTTP 400 responses. Magnitudes are optional but when
    supplied must contain all elements. Multiple magnitudes can be delimited
    by a comma.
    """

    # Form fields
    obsid = forms.MultipleChoiceField(choices=obs_choices())
    ready = forms.ChoiceField(
        initial="true",
        choices=(("true", "Yes"), ("false", "No")),
    )
    brightness = forms.FloatField(required=False, label="Target Brightness")
    brightness_system = forms.ChoiceField(
        required=False,
        initial="AB",
        label="Brightness System",
        choices=(("Vega", "Vega"), ("AB", "AB"), ("Jy", "Jy")),
    )
    brightness_band = forms.ChoiceField(
        required=False,
        initial="r",
        label="Brightness Band",
        choices=(
            ("u", "u"),
            ("U", "U"),
            ("B", "B"),
            ("g", "g"),
            ("V", "V"),
            ("UC", "UC"),
            ("r", "r"),
            ("R", "R"),
            ("i", "i"),
            ("I", "I"),
            ("z", "z"),
            ("Y", "Y"),
            ("J", "J"),
            ("H", "H"),
            ("K", "K"),
            ("L", "L"),
            ("M", "M"),
            ("N", "N"),
            ("Q", "Q"),
            ("AP", "AP"),
        ),
    )
    posangle = forms.FloatField(
        min_value=0.0,
        max_value=360.0,
        required=False,
        initial=0.0,
        label="Position Angle",
    )

    exptimes = forms.CharField(required=False, label="Exptime(s) [s]")

    group = forms.CharField(required=False, label="Group Name")
    notetitle = forms.CharField(
        required=False,
        initial="Finding Chart",
        label="Note Title",
    )
    note = forms.CharField(required=False, label="Note Text")

    eltype = forms.ChoiceField(
        required=False,
        label="Airmass/Hour Angle",
        choices=(("none", "None"), ("airmass", "Airmass"), ("hourAngle", "Hour Angle")),
    )
    elmin = forms.FloatField(
        required=False,
        min_value=-5.0,
        max_value=5.0,
        label="Min Airmass/HA",
        initial=1.0,
    )
    elmax = forms.FloatField(
        required=False,
        min_value=-5.0,
        max_value=5.0,
        label="Max Airmass/HA",
        initial=2.0,
    )

    gstarg = forms.CharField(required=False, label="Guide Star Name")
    gsra = forms.CharField(required=False, label="Guide Star RA")
    gsdec = forms.CharField(required=False, label="Guide Star Dec")
    gsbrightness = forms.FloatField(required=False, label="Guide Star Brightness")
    gsbrightness_system = forms.ChoiceField(
        required=False,
        initial="Vega",
        label="Brightness System",
        choices=(("Vega", "Vega"), ("AB", "AB"), ("Jy", "Jy")),
    )
    gsbrightness_band = forms.ChoiceField(
        required=False,
        initial="UC",
        label="Brightness Band",
        choices=(
            ("UP", "u"),
            ("U", "U"),
            ("B", "B"),
            ("GP", "g"),
            ("V", "V"),
            ("UC", "UC"),
            ("RP", "r"),
            ("R", "R"),
            ("IP", "i"),
            ("I", "I"),
            ("ZP", "z"),
            ("Y", "Y"),
            ("J", "J"),
            ("H", "H"),
            ("K", "K"),
            ("L", "L"),
            ("M", "M"),
            ("N", "N"),
            ("Q", "Q"),
            ("AP", "AP"),
        ),
    )
    gsprobe = forms.ChoiceField(
        required=False,
        label="Guide Probe",
        initial="OIWFS",
        choices=(
            ("OIWFS", "OIWFS"),
            ("PWFS1", "PWFS1"),
            ("PWFS2", "PWFS2"),
            ("AOWFS", "AOWFS"),
        ),
    )
    window_start = forms.CharField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime"},
            format="%Y-%m-%d %H:%M:%S",
        ),
        label="Timing Window",
    )
    window_duration = forms.IntegerField(
        required=False,
        min_value=1,
        label="Window Duration [hr]",
    )

    def layout(self):
        return Div(
            HTML("<big>Observation Parameters</big>"),
            HTML("<p>Select the Obsids of one or more templates. <br>"),
            HTML("Setting Ready=No will keep the new observation(s) On Hold. <br>"),
            HTML("If a value is not set, then the template default is used. <br>"),
            HTML(
                "If setting Exptime, then provide a list of values if selecting more than one Obsid.</p>",
            ),
            Div(
                Div("obsid", css_class="col"),
                Div("ready", css_class="col"),
                Div("notetitle", css_class="col"),
                css_class="form-row",
            ),
            Div(
                Div("posangle", "brightness", "eltype", "group", css_class="col"),
                Div(
                    "exptimes",
                    "brightness_band",
                    "elmin",
                    "window_start",
                    css_class="col",
                ),
                Div(
                    "note",
                    "brightness_system",
                    "elmax",
                    "window_duration",
                    css_class="col",
                ),
                css_class="form-row",
            ),
            HTML("<big>Optional Guide Star Parameters</big>"),
            HTML("<p>If any one of Name/RA/Dec is given, then all must be.</p>"),
            Div(
                Div("gstarg", "gsbrightness", "gsprobe", css_class="col"),
                Div("gsra", "gsbrightness_band", css_class="col"),
                Div("gsdec", "gsbrightness_system", css_class="col"),
                css_class="form-row",
            ),
        )

    def validate_at_facility(self) -> dict:
        """Calls validation for the facility.

        Returns
        -------
        `dict`
            Errors, if any.

        """
        obs_module = get_service_class(self.cleaned_data["facility"])
        return obs_module().validate_observation(self.observation_payload())

    def is_valid(self):
        super().is_valid()
        errors = self.validate_at_facility()
        if errors:
            self.add_error(None, flatten_error_dict(self, errors))
        return not errors

    def observation_payload(self):
        def isodatetime(value):
            isostring = parse(value).isoformat()
            ii = isostring.find("T")
            time_ii = ii + 1
            date = isostring[0:ii]
            time = isostring[time_ii:]
            return date, time

        payloads = []

        target = Target.objects.get(pk=self.cleaned_data["target_id"])
        spa = str(self.cleaned_data["posangle"]).strip()

        nobs = len(self.cleaned_data["obsid"])
        if self.cleaned_data["exptimes"] != "":
            expvalues = self.cleaned_data["exptimes"].split(",")
            if len(expvalues) != nobs:
                payloads.append(
                    {
                        "error": (
                            "If exptimes given, the number of values must equal the number of obsids "
                            "selected."
                        ),
                    },
                )
                return payloads

            # Convert exposure times to integers
            exptimes = []
            try:
                [exptimes.append(round(float(exp))) for exp in expvalues]
            except Exception:
                payloads.append({"error": "Problem converting string to integer."})
                return payloads

        for jj in range(nobs):
            obs = self.cleaned_data["obsid"][jj]
            ii = obs.rfind("-")
            obsnum_ii = ii + 1
            progid = obs[0:ii]
            obsnum = obs[obsnum_ii:]
            payload = {
                "prog": progid,
                "obsnum": obsnum,
                "target": target.name,
                "ra": target.ra,
                "dec": target.dec,
                "ready": self.cleaned_data["ready"],
            }

            if (
                self.cleaned_data["notetitle"] != "Finding Chart"
                or self.cleaned_data["note"] != ""
            ):
                payload["noteTitle"] = self.cleaned_data["notetitle"]
                payload["note"] = self.cleaned_data["note"]

            if self.cleaned_data["brightness"] is not None:
                smags = (
                    str(self.cleaned_data["brightness"]).strip()
                    + "/"
                    + self.cleaned_data["brightness_band"]
                    + "/"
                    + self.cleaned_data["brightness_system"]
                )
                payload["mags"] = smags

            if self.cleaned_data["exptimes"] != "":
                payload["exptime"] = exptimes[jj]

            if self.cleaned_data["group"].strip() != "":
                payload["group"] = self.cleaned_data["group"].strip()

            # timing window?
            if self.cleaned_data["window_start"].strip() != "":
                wdate, wtime = isodatetime(self.cleaned_data["window_start"])
                payload["windowDate"] = wdate
                payload["windowTime"] = wtime
                payload["windowDuration"] = str(
                    self.cleaned_data["window_duration"],
                ).strip()

            # elevation/airmass
            if self.cleaned_data["eltype"] is not None:
                payload["elevationType"] = self.cleaned_data["eltype"]
                payload["elevationMin"] = str(self.cleaned_data["elmin"]).strip()
                payload["elevationMax"] = str(self.cleaned_data["elmax"]).strip()

            # Guide star
            gstarg = self.cleaned_data["gstarg"]
            if gstarg != "":
                gsra = self.cleaned_data["gsra"]
                gsdec = self.cleaned_data["gsdec"]
                if self.cleaned_data["gsbrightness"] is not None:
                    sgsmag = (
                        str(self.cleaned_data["gsbrightness"]).strip()
                        + "/"
                        + self.cleaned_data["gsbrightness_band"]
                        + "/"
                        + self.cleaned_data["gsbrightness_system"]
                    )

            if gstarg != "":
                payload["gstarget"] = gstarg
                payload["gsra"] = gsra
                payload["gsdec"] = gsdec
                payload["gsmags"] = sgsmag
                payload["gsprobe"] = self.cleaned_data["gsprobe"]

            payload["posangle"] = spa

            payloads.append(payload)

        return payloads


class GOATSGEMFacility(BaseRoboticObservationFacility):
    """The ``GEMFacility`` is the interface to the Gemini Telescope. For
    information regarding Gemini observing and the available parameters, please
    see https://www.gemini.edu/observing/start-here
    """

    name = "GEM"
    observation_forms = {"OBSERVATION": GEMObservationForm}

    def get_form(self, observation_type):
        """Always returns the Gemini Observation Form for now."""
        return GEMObservationForm

    def submit_observation(self, observation_payload: list[dict[str, Any]]):
        obsids = []
        for payload in observation_payload:
            # TODO: Remove after work to the OCS.
            payload["email"] = "ocs@test.com"

            # Get the correct key to use in the request.
            # TODO: Add in retry with user key if these fail, need to
            # investigate how gemini rejects.
            key_info = get_key_info(self.user, identifier=payload["prog"])
            payload.update(key_info)

            response = make_request(
                "POST",
                PORTAL_URL[get_site(payload["prog"])] + "/too",
                verify=False,
                params=payload,
            )
            # Return just observation number
            obsid = response.text.split("-")
            obsids.append(obsid[-1])
        return obsids

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

        # Validate the program ID.
        observation_id = (
            f"{observation_payload[0]['prog']}-{observation_payload[0]['obsnum']}"
        )
        if not GeminiID.is_valid_observation_id(observation_id):
            errors["obs"] = f"Observation ID {observation_id} is not valid."

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
        return {}

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
        return {}

    def cancel_observation(self, observation_id):
        """Takes an observation id and submits a request to the observatory that
        the observation be cancelled.

        If the cancellation was successful, return True. Otherwise, return
        False.
        """
        raise NotImplementedError(
            "This facility has not implemented cancel observation.",
        )

    def get_date_obs_from_fits_header(self, header):
        date_obs = header.get("DATE-OBS")  # Observation date
        time_obs = header.get("TIME-OBS")  # Observation time

        if date_obs and time_obs:
            # Combine date and time
            return f"{date_obs} {time_obs}"

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
