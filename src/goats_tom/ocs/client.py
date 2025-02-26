"""This module contains the OCSClient class, a dedicated client for interacting
with the Gemini Observatory's Observation Control Software (OCS).

The OCSClient class is designed to facilitate the retrieval and parsing of data
from the Gemini Observatory's databases.
"""

__all__ = ["OCSClient"]

import ssl
import xmlrpc.client
from typing import Any

import requests
import urllib3

from .gemini_id import GeminiID
from .parser import OCSParser

# Disable warnings about insecure HTTP connection for now.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OCSClient:
    """A client for interacting with the Gemini Observatory's OCS
    (Observation Control System).

    This client provides methods to retrieve and parse observation sequence
    data and coordinates from the Gemini Observatory's databases.

    Each method in this class returns a dictionary with the structure:
    - success (bool): Indicates whether the request was successful.
    - data (dict[str, Any] | None): Contains the parsed data if the request
      was successful. Structure varies depending on the method.
    - raw_data (str | None): Contains the raw XML data if 'skip_parsing'
      is True.
    - error (str | None): Contains the error message if the request failed.

    Attributes
    ----------
    method_names : `dict[str, str]`
        A mapping of method names for XML-RPC calls. Maps the functionality
        (like ``get_sequence``, ``get_coordinates``) to their corresponding
        XML-RPC method names.
    site_urls : `dict[str, Any]`
        The base URLs for the Gemini South (GS) and Gemini North (GN)
        observatories, including their respective hosts and port numbers.
    odb_url : `str`
        The endpoint for querying observation database (ODB) information.
    wdba_url : `str`
        The endpoint for interacting with the Web Database Access (WDBA)
        interface.

    """

    method_names = {
        "get_sequence": "WDBA_Exec.getSequence",
        "get_coordinates": "WDBA_Tcc.getCoordinates",
    }
    site_urls = {
        "GS": {"host": "https://gsodb.gemini.edu", "port": 8443},
        "GN": {"host": "https://gnodb.gemini.edu", "port": 8443},
    }
    odb_url = "/odbbrowser/targets?programReference="
    wdba_url = "/wdba"

    def __init__(self):
        self.parser = OCSParser()

    def _get_site_url(self, site: str) -> str:
        """Determines the site URL based on the site.

        Parameters
        ----------
        site : `str`
            The site.

        Returns
        -------
        `str`
            The site URL.

        Raises
        ------
        ValueError
            Raised if the site is not recognized.

        """
        site_info = self.site_urls.get(site)
        if not site_info:
            raise ValueError(f"Site not recognized in {site}")
        return f"{site_info['host']}:{site_info['port']}"

    def _send_request(
        self, program_or_observation_id: str, method_name: str | None = None,
    ) -> dict[str, Any]:
        """Sends a request to the OCS server, handling both WDBA and ODB
        requests.

        Parameters
        ----------
        program_or_observation_id : `str`
            The program/observation ID for which the request is being made.
        method_name : `str | None`
            The name of the WDBA method to call, if this is a WDBA request.

        Returns
        -------
        `dict[str, Any]`
            The response from the server.

        Raises
        ------
        Exception
            Raised if there's an error in the request.

        """
        try:
            gemini_id = GeminiID(program_or_observation_id)
            base_url = self._get_site_url(gemini_id.site)

            if method_name is not None:
                url = f"{base_url}{self.wdba_url}"

                # Bypass the expired certificate.
                context = ssl._create_unverified_context()

                # Get the method and call it.
                with xmlrpc.client.ServerProxy(url, context=context) as proxy:
                    raw_data = getattr(proxy, method_name)(gemini_id.observation_id)

                return {"success": True, "raw_data": raw_data}

            full_url = f"{base_url}{self.odb_url}{gemini_id.program_id}"

            # Use verify=False to bypass expired certificate.
            response = requests.get(full_url, verify=False, timeout=3)
            response.raise_for_status()
            return {"success": True, "raw_data": response.text}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_program_summary(
        self, program_or_observation_id: str, skip_parsing: bool | None = False,
    ) -> dict[str, Any]:
        """Fetches summary for a program ID.

        Parameters
        ----------
        program_or_observation_id : `str`
            The program or observation ID.
        skip_parsing : `bool | None`
            Skips parsing and returns the raw XML data.

        Returns
        -------
        `dict[str, Any]`
            Program summary.

        """
        response = self._send_request(program_or_observation_id)
        if not response["success"] or skip_parsing:
            return response

        response["data"] = self.parser.parse_odb_response(response["raw_data"])
        del response["raw_data"]

        return response

    def get_observation_summary(
        self, observation_id: str, skip_parsing: bool | None = False,
    ) -> dict[str, Any]:
        """Fetches summary for an observation ID.

        Parameters
        ----------
        observation_id : `str`
            The observation ID.
        skip_parsing : `bool | None`
            Skips parsing and returns the raw XML data.

        Returns
        -------
        `dict[str, Any]`
            Observation summary.

        """
        response = self._send_request(observation_id)
        if not response["success"] or skip_parsing:
            return response
        parsed_response = self.parser.parse_odb_response(response["raw_data"])
        del response["raw_data"]

        observations = parsed_response.get("observations", {}).get("observation", [])

        # Search for matching observation ID.
        for observation in observations:
            if observation.get("id") == observation_id:
                response["data"] = observation
                return response

        # Return error if the observation ID is missing from the program ID.
        gemini_id = GeminiID(observation_id)
        return {
            "success": False,
            "error": (
                f"Program '{gemini_id.program_id}' does not have observation "
                f"'{gemini_id.observation_id}'"
            ),
        }

    def get_sequence(
        self, observation_id: str, skip_parsing: bool | None = False,
    ) -> dict[str, Any]:
        """Fetches the sequence data for a given observation ID.

        Parameters
        ----------
        observation_id : `str`
            The observation ID to query.
        skip_parsing : `bool | None`
            Skips parsing and returns the raw XML data.

        Returns
        -------
        `dict[str, Any]`
            The response from the server.

        """
        response = self._send_request(
            observation_id, method_name=self.method_names["get_sequence"],
        )
        if not response["success"] or skip_parsing:
            return response
        response["data"] = self.parser.parse_sequence_response(response["raw_data"])
        del response["raw_data"]

        return response

    def get_coordinates(
        self, observation_id: str, skip_parsing: bool | None = False,
    ) -> dict[str, Any]:
        """Fetches the coordinates for a given observation ID.

        Parameters
        ----------
        observation_id : `str`
            The observation ID to query.
        skip_parsing : `bool | None`
            Skips parsing and returns the raw XML data.

        Returns
        -------
        `dict[str, Any]`
            The response from the server.

        """
        response = self._send_request(
            observation_id, method_name=self.method_names["get_coordinates"],
        )
        if not response["success"] or skip_parsing:
            return response
        response["data"] = self.parser.parse_coordinates_response(response["raw_data"])
        del response["raw_data"]

        return response
