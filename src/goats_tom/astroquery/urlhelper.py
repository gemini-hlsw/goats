"""
Query public and proprietary data from GOA.
"""

__all__ = ["URLHelper"]

from astropy import units
from astropy.coordinates import Angle
from astroquery.utils import commons

from .conf import conf


def handle_keyword_arg(key, value):
    """Handler function for generic keyword argument."""
    return f"{key}={value}"


def handle_radius(key, radius):
    """Handler function for radius keyword with smart conversion to a degrees
    value.
    """
    if key != "radius":
        raise ValueError('Handler only works for "radius" keywords.')

    if isinstance(radius, (int, float)):
        radius = radius * units.deg

    radius = Angle(radius)

    return f"sr={radius.deg}d"


def handle_coordinates(key, coordinates):
    """Handler function for coordinates."""
    if key != "coordinates":
        raise ValueError('Handler only works for "coordinates" keywords.')

    coordinates = commons.parse_coordinates(coordinates)
    return f"ra={coordinates.ra.deg}/dec={coordinates.dec.deg}"


handlers = {
    "radius": handle_radius,
    "coordinates": handle_coordinates,
    "default": handle_keyword_arg,
}


class URLHelper:
    ENGINEERING_PARAMETERS = {"notengineering", "engineering", "includeengineering"}
    QA_PARAMETERS = {
        "NotFail",
        "AnyQA",
        "Pass",
        "Lucky",
        "Win",
        "Usable",
        "Undefind",
        "Fail",
    }
    FILE_CURATION_PARAMETERS = {"present", "canonical", "notpresent", "notcanonical"}
    ENDPOINTS = {
        "summary": "/jsonsummary",
        "file_list": "/jsonfilelist",
        "tar_file": "/download",
        "file": "/file",
        "login": "/login",
        "search": "/searchform",
    }
    VALID_ENDPOINTS = set(ENDPOINTS.keys())

    def __init__(self):
        """Make a URL Helper for building URLs to the Gemini Archive REST
        service.
        """
        self.server = conf.GOA_SERVER

    def get_login_url(self):
        """Wrapper for getting login URL."""
        return f"{self.server}{self.ENDPOINTS['login']}"

    def get_summary_url(self, *args, **kwargs):
        """Wrapper for getting JSON summary URL."""
        return self.build_url(*args, endpoint="summary", **kwargs)

    def get_file_list_url(self, *args, **kwargs):
        """Wrapper for getting JSON file list URL."""
        return self.build_url(*args, endpoint="file_list", **kwargs)

    def get_tar_file_url(self, *args, **kwargs):
        """Wrapper for getting tar file URL."""
        return self.build_url(*args, endpoint="tar_file", **kwargs)

    def get_file_url(self, filename):
        """Wrapper for getting single file URL."""
        return f"{self.server}{self.ENDPOINTS['file']}/{filename}"

    def get_search_url(self, program_id):
        """Wrapper for getting the search URL for a program ID."""
        return f"{self.server}{self.ENDPOINTS['search']}/{program_id}"

    def build_url(self, *args, endpoint=None, **kwargs):
        """Build a URL with the given args and kwargs as the query parameters.

        Parameters
        ----------
        args : list
            The arguments to be passed in the URL without a key.  Each of
            these is simply added as another component of the path in the url.
        kwargs : dict of key/value parameters for the url
            The arguments to be passed in key=value form.

        Returns
        -------
        response : `string` url to execute the query

        """
        if endpoint is not None and endpoint not in self.VALID_ENDPOINTS:
            raise ValueError(
                f"GOA URL endpoint ({endpoint}) must be: "
                f"{', '.join(self.VALID_ENDPOINTS)}"
            )

        if endpoint is None:
            endpoint = "summary"
        elif endpoint == "file":
            # Must handle file url differently.
            return self.get_file_url(args[0])
        elif endpoint == "login":
            return self.get_login_url()
        elif endpoint == "search":
            return self.get_search_url(args[0])

        url_endpoint = self.ENDPOINTS[endpoint]

        # Get default values that are needed in API.
        eng_parm = next(
            (a for a in args if a in self.ENGINEERING_PARAMETERS),
            "notengineering",
        )

        qa_parm = next((a for a in args if a in self.QA_PARAMETERS), "NotFail")

        file_curation_param = next(
            (a for a in args if a in self.FILE_CURATION_PARAMETERS),
            "canonical",
        )

        # Filter out defaults from args.
        args = [a for a in args if a not in [eng_parm, qa_parm, file_curation_param]]

        path_parts = [url_endpoint, eng_parm, qa_parm]
        path_parts.extend(args)

        # Include kwargs in the URL path.
        orderby = kwargs.pop("orderby", None)
        for key, value in kwargs.items():
            handler = handlers.get(key, handle_keyword_arg)
            path_parts.append(handler(key, value))

        path = "/".join(path_parts)

        query_string = ""
        if orderby is not None:
            query_string = f"?orderby={orderby}"

        print(f"{self.server}{path}{query_string}")

        return f"{self.server}{path}{query_string}"
