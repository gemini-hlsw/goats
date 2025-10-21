from importlib.metadata import version as get_version
from json import JSONDecodeError

import requests
from packaging.version import InvalidVersion, Version

from goats_cli.exceptions import GOATSClickException

CHANNELDATA_URL = "https://gemini-hlsw.github.io/goats-infra/conda/channeldata.json"


class VersionChecker:
    """
    Compare the installed GOATS version against the latest available in the channel.

    Parameters
    ----------
    channeldata_url : str, optional
        URL to the ``channeldata.json`` file used to resolve the latest version.
        Defaults to ``CHANNELDATA_URL``.
    package_name : str, optional
        Package name whose installed version is obtained via
        ``importlib.metadata.version``. Defaults to ``"goats"``.
    timeout_sec : float, optional
        HTTP request timeout in seconds. Defaults to ``1.0``.

    Attributes
    ----------
    channeldata_url : str
        URL used to query the latest available version.
    package_name : str
        Package name used to resolve the installed version.
    timeout_sec : float
        Timeout applied to the HTTP request.
    current_version : str | None
        Installed package version (``None`` until computed).
    latest_version : str | None
        Latest available version from the channel (``None`` until computed).
    is_outdated : bool | None
        ``True`` if ``current_version < latest_version``, ``False`` otherwise
        (``None`` until computed).
    """

    def __init__(
        self,
        channeldata_url: str = CHANNELDATA_URL,
        package_name: str = "goats",
        timeout_sec: float = 1.0,
    ) -> None:
        """
        Initialize a :class:`VersionChecker` instance.

        Parameters
        ----------
        channeldata_url : str, optional
            URL to the channel metadata JSON. Defaults to ``CHANNELDATA_URL``.
        package_name : str, optional
            Package name to inspect. Defaults to ``"goats"``.
        timeout_sec : float, optional
            Timeout (seconds) for HTTP requests. Defaults to ``1.0``.
        """
        self.channeldata_url = channeldata_url
        self.package_name = package_name
        self.timeout_sec = timeout_sec

        self.current_version: str | None = None
        self.latest_version: str | None = None
        self.is_outdated: bool | None = None

    def _get_current_version(self) -> str:
        """
        Return the currently installed version string for ``self.package_name``.

        Returns
        -------
        str
            Installed version string (e.g., ``"1.2.3"``).

        Raises
        ------
        importlib.metadata.PackageNotFoundError
            If the package is not installed in the current environment.
        """
        return get_version(self.package_name).strip()

    def _get_latest_version(self) -> str:
        """
        Fetch the latest available version string from the Conda channel.

        Returns
        -------
        str
            Latest version string for ``self.package_name`` (e.g., ``"1.2.3"``).

        Raises
        ------
        GOATSClickException
            If a network/HTTP error occurs, the response payload is invalid JSON,
            or the JSON structure does not contain the expected keys.
        """
        try:
            resp = requests.get(self.channeldata_url, timeout=self.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            return data["packages"][self.package_name]["version"].strip()
        except requests.RequestException as error:
            raise GOATSClickException(f"Failed to fetch latest version info: {error}")
        except JSONDecodeError as error:
            raise GOATSClickException(f"Invalid JSON: {error}")
        except (KeyError, TypeError) as error:
            raise GOATSClickException(
                f"Malformed channel metadata while obtaining latest version: {error}"
            )

    def check_if_outdated(self) -> bool:
        """
        Resolve both installed and latest versions and update the instance state.

        This method always re-queries the environment and the channel:
        it refreshes :attr:`current_version`, :attr:`latest_version`, and
        recomputes :attr:`is_outdated`.

        Returns
        -------
        bool
            ``True`` if an update is available (``installed < latest``),
            otherwise ``False``.

        Raises
        ------
        GOATSClickException
            If fetching/parsing the channel metadata fails, or if either version
            string is invalid (invalid PEP 440 format).
        """
        self.current_version = self._get_current_version()
        self.latest_version = self._get_latest_version()
        try:
            self.is_outdated = Version(self.current_version) < Version(
                self.latest_version
            )
            return self.is_outdated
        except InvalidVersion as error:
            raise GOATSClickException(
                "Invalid version string while comparing versions: "
                f"current={self.current_version!r}, "
                f"latest={self.latest_version!r}"
            ) from error
