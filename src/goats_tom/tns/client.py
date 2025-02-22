"""Module for scraping the TNS website."""

__all__ = ["TNSClient"]

import requests
from bs4 import BeautifulSoup


class TNSClient:
    """Client for querying objects from the TNS website.

    Parameters
    ----------
    timeout : `float`, optional
            Request timeout in seconds, by default 10.0
    """

    BASE_URL: str = "https://www.wis-tns.org/object"
    USER_AGENT: str = "GOATS.TNSClient/1.0"

    # Map of container classes to the user-facing field names.
    # 'radec' is handled separately so we can split it into RA and DEC.
    FIELDS_MAP: dict[str, str] = {
        "type": "field-type",
        "redshift": "field-redshift",
        "reporting_group": "field-reporting_group_name",
        "discovering_data_source": "field-source_group_name",
        "discovery_date": "field-discoverydate",
        "tns_at": "field-isTNS_AT",
        "public": "field-public",
        "discovery_magnitude": "field-discoverymag",
        "filter": "field-filter_name",
        "radec": "field-radec",
    }

    def __init__(
        self,
        timeout: float = 10.0,
    ) -> None:
        self.timeout: float = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.USER_AGENT})

    def get_object(self, object_name: str) -> dict[str, str | None]:
        """Retrieve the raw HTML for a given TNS object.

        Parameters
        ----------
        object_name : `str`
            Name of the object to query on TNS.

        Returns
        -------
        `dict[str, str | None]`
            A dictionary with keys for each field defined in FIELDS_MAP,
            plus 'right_ascension' and 'declination' for RA/DEC and object name.
            Fields will be `None` if they cannot be found.

        Raises
        ------
        requests.HTTPError
            If the request fails with a non-2xx status code.
        """
        url = f"{self.BASE_URL}/{object_name}"
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()

        html = response.text

        return self._parse_object_html(html)

    def _parse_object_html(self, html: str) -> dict[str, str | None]:
        """Parse the provided HTML to extract TNS fields into a dictionary.

        Parameters
        ----------
        html : `str`
            Raw HTML of the TNS object page.

        Returns
        -------
        `dict[str, str | None]`
            A dictionary with keys for each field defined in FIELDS_MAP,
            plus 'right_ascension' and 'declination' for RA/DEC and object name.
            Fields will be `None` if they cannot be found.
        """
        result: dict[str, str | None] = {}
        soup = BeautifulSoup(html, "html.parser")

        # Extract title text for the object name with the prefix.
        result["name"] = self._parse_object_name_from_title(soup)

        # Loop through the fields and build the result payload.
        for field_name, container_class in self.FIELDS_MAP.items():
            raw_value = self._parse_value_from_div_container(soup, container_class)
            result[field_name] = raw_value

        # Handle the right ascension and declination.
        radec = result.pop("radec", None)
        result["right_ascension"], result["declination"] = self._parse_radec_from_value(
            radec
        )

        return result

    def _parse_object_name_from_title(self, soup: BeautifulSoup) -> str | None:
        """Extracts the object name from the page title.

        Parameters
        ----------
        soup : `BeautifulSoup`
            A `BeautifulSoup` object representing the parsed HTML content.

        Returns
        -------
        `str | None`
            The object name extracted from the title tag if it exists, otherwise `None`.
        """
        title_tag = soup.find("h1", id="page-title")
        return title_tag.get_text(strip=True) if title_tag else None

    def _parse_value_from_div_container(
        self, soup: BeautifulSoup, container_class: str
    ) -> str | None:
        """Find and return the text of the nested '.value' div within a container of a
        given class.

        Parameters
        ----------
        soup : `BeautifulSoup`
            Parsed HTML soup.
        container_class : `str`
            Class name of the container div.

        Returns
        -------
        `str | None`
            Text content stripped of whitespace, or `None` if not found.
        """
        container = soup.find("div", class_=container_class)
        if not container:
            return None
        value_div = container.find("div", class_="value")
        if not value_div:
            return None
        return value_div.get_text(strip=True)

    def _parse_radec_from_value(
        self, value: str | None
    ) -> tuple[str | None, str | None]:
        """Parses the Right Ascension and Declination from a string.

        Parameters
        ----------
        value : `str | None`
            A string containing the Right Ascension and Declination separated by
            whitespace.

        Returns
        -------
        `tuple[str | None, str | None]`
            A tuple containing the Right Ascension and Declination as strings. If
            parsing fails, `None` is returned for both values.
        """
        right_ascension = None
        declination = None
        if value is None:
            return right_ascension, declination

        parts = value.split(maxsplit=1)
        if len(parts) == 2:
            right_ascension, declination = parts

        return right_ascension, declination
