from importlib.metadata import version as get_version
from json import JSONDecodeError

import requests
from packaging.version import Version

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
        HTTP request timeout in seconds. Defaults to ``10.0``.

    Attributes
    ----------
    channeldata_url : str
        URL used to query the latest available version.
    package_name : str
        Package name used to resolve the installed version.
    timeout_sec : float
        Timeout applied to the HTTP request.
    current_version : str
        Installed package version, stripped.
    latest_version : str
        Latest available version from the channel, stripped.
    is_outdated : bool
        ``True`` if ``current_version < latest_version``; ``False`` otherwise.

    Raises
    ------
    GOATSClickException
        If a network/HTTP error occurs or if the channel JSON payload is malformed
        while resolving ``latest_version``.
    """

    def __init__(
        self,
        channeldata_url: str = CHANNELDATA_URL,
        package_name: str = "goats",
        timeout_sec: float = 10.0,
    ) -> None:
        self.channeldata_url = channeldata_url
        self.package_name = package_name
        self.timeout_sec = timeout_sec

        self.current_version: str = get_version(self.package_name).strip()
        self.latest_version: str = self._get_latest_version().strip()

        # Boolean flag indicating whether an update is available.
        self.is_outdated: bool = Version(self.current_version) < Version(
            self.latest_version
        )

    def _get_latest_version(self) -> str:
        """
        Fetch the latest version string for the package from the Conda channel.

        Returns
        -------
        str
            Latest version string for ``self.package_name`` (e.g., ``"1.2.3"``).

        Raises
        ------
        GOATSClickException
            If a network/HTTP error occurs during the download or if the JSON payload
            lacks the expected structure (``packages -> <package_name> -> version``).
        """
        try:
            resp = requests.get(self.channeldata_url, timeout=self.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            return data["packages"][self.package_name]["version"]
        except requests.RequestException as error:
            raise GOATSClickException(f"Failed to fetch latest version info: {error}")
        except JSONDecodeError as error:
            raise GOATSClickException(f"Invalid JSON: {error}")
        except (KeyError, TypeError) as error:
            raise GOATSClickException(
                f"Malformed channel metadata while obtaining latest version: {error}"
            )
