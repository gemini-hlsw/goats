"""
Version checker for the GOATS package.
"""

__all__ = ["VersionChecker"]

import logging
from functools import cached_property
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from json import JSONDecodeError

import requests
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

__all__ = ["VersionChecker"]

CHANNELDATA_URL = "https://gemini-hlsw.github.io/goats-infra/conda/channeldata.json"
PACKAGE_NAME = "goats"


class VersionChecker:
    """
    Compare the installed package version against the latest available version
    from a Conda-style ``channeldata.json`` file.

    Parameters
    ----------
    channeldata_url : str=CHANNELDATA_URL
        URL to the ``channeldata.json`` file used to resolve the latest version.
    package_name : str=PACKAGE_NAME
        Package name whose installed version is obtained via
        ``importlib.metadata.version``.
    timeout_sec : float=5.0
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        channeldata_url: str = CHANNELDATA_URL,
        package_name: str = PACKAGE_NAME,
        timeout_sec: float = 5.0,
    ) -> None:
        self.channeldata_url = channeldata_url
        self.package_name = package_name
        self.timeout_sec = timeout_sec
        self._errors: list[str] = []

    @cached_property
    def current_version(self) -> str | None:
        """
        Get the currently installed version of the package.

        Returns
        -------
        str | None
            Installed version string if the package is found; otherwise ``None``.

        """
        try:
            return get_version(self.package_name).strip()
        except PackageNotFoundError:
            msg = f"Package {self.package_name!r} not found"
            logger.warning(msg)
            self._errors.append(msg)

        return None

    @cached_property
    def latest_version(self) -> str | None:
        """
        Fetch the latest available version from the channeldata.json file.

        Returns
        -------
        str | None
            Latest version string if successfully retrieved; otherwise ``None``.
        """
        try:
            resp = requests.get(self.channeldata_url, timeout=self.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            return data["packages"][self.package_name]["version"].strip()

        except requests.Timeout as e:
            msg = f"Timed out fetching channel metadata: {e}"
        except requests.RequestException as e:
            msg = f"Failed to fetch latest version: {e}"
        except JSONDecodeError as e:
            msg = f"Invalid JSON from channel: {e}"
        except (KeyError, TypeError) as e:
            msg = f"Malformed channeldata.json: {e}"
        except Exception as e:
            msg = f"Unexpected error fetching latest version: {e}"

        logger.warning(msg)
        self._errors.append(msg)

        return None

    @cached_property
    def is_outdated(self) -> bool | None:
        """
        Determine if the installed version is older than the latest version.

        Returns
        -------
        bool | None
            ``True`` if the installed version is older, ``False`` if up-to-date,
            or ``None`` if the comparison could not be made.
        """
        if self.current_version is None or self.latest_version is None:
            return None
        try:
            return Version(self.current_version) < Version(self.latest_version)
        except InvalidVersion as e:
            msg = (
                f"Invalid version format: current={self.current_version!r}, "
                f"latest={self.latest_version!r} ({e})"
            )
            logger.warning(msg)
            self._errors.append(msg)

            return None

    def refresh(self) -> None:
        """
        Clear all cached properties. Use before rechecking.
        """
        for attr in ("current_version", "latest_version", "is_outdated"):
            self.__dict__.pop(attr, None)

    def as_dict(self) -> dict[str, str | None | bool | list[str]]:
        """
        Return version information as a dictionary.

        Returns
        -------
        dict[str, str | None | bool | list[str]]
            Dictionary containing package name, current version, latest version,
            whether it is outdated, status, and any errors encountered.
        """
        # Determine if all version info is valid.
        is_valid = (
            self.current_version is not None
            and self.latest_version is not None
            and self.is_outdated is not None
        )

        # Construct the result dictionary.
        result: dict[str, str | None | bool | list[str]] = {
            "package": self.package_name,
            "current": self.current_version,
            "latest": self.latest_version,
            "is_outdated": self.is_outdated,
            "status": "success" if is_valid else "error",
        }

        # Include errors if any.
        if self._errors:
            result["errors"] = self._errors.copy()

        return result
