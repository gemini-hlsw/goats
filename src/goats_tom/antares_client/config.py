"""
ANTARES client configuration module. Defines default settings for connecting to the
ANTARES API, including environment, base URLs, and timeouts.
"""

__all__ = ["ANTARESConfig"]

import logging
from dataclasses import dataclass, field
from enum import Enum

from django.conf import settings

logger = logging.getLogger(__name__)


class AntaresEnvironment(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class _ANTARESConfig:
    """
    Default configuration for the ANTARES client.

    Attributes
    ----------
    timeout : int
        Default timeout for API requests in seconds.
    environment : AntaresEnvironment
        Default ANTARES environment.
    api_urls : dict[AntaresEnvironment, str]
        Mapping of ANTARES environments to their respective API base URLs.
    urls : dict[AntaresEnvironment, str]
        Mapping of ANTARES environments to their respective base URLs.
    """

    timeout: int = 60
    environment: AntaresEnvironment = AntaresEnvironment.PRODUCTION
    api_urls: dict[AntaresEnvironment, str] = field(
        default_factory=lambda: {
            AntaresEnvironment.DEVELOPMENT: "https://api.development.antares.noirlab.edu/v1/",
            AntaresEnvironment.PRODUCTION: "https://api.antares.noirlab.edu/v1/",
        }
    )
    urls: dict[AntaresEnvironment, str] = field(
        default_factory=lambda: {
            AntaresEnvironment.DEVELOPMENT: "https://development.antares.noirlab.edu",
            AntaresEnvironment.PRODUCTION: "https://antares.noirlab.edu",
        }
    )

    def get_environment(self) -> AntaresEnvironment:
        """
        Get the ANTARES environment from Django settings.

        Returns
        -------
        AntaresEnvironment
            The ANTARES environment.

        Raises
        -------
        ValueError
            If the ANTARES_ENV setting is invalid.
        """
        # Get the environment string from settings or use the default.
        env_str = getattr(settings, "ANTARES_ENV", self.environment.value)
        try:
            return AntaresEnvironment(env_str)
        except ValueError as exc:
            raise ValueError(
                f"Invalid ANTARES_ENV '{env_str}'. Must be one of: "
                f"{', '.join([e.value for e in AntaresEnvironment])}."
            ) from exc

    def get_api_url(self) -> str:
        """
        Get the ANTARES API base URL from Django settings.

        Returns
        -------
        str
            The ANTARES API base URL.

        Raises
        ------
        ValueError
            If the ANTARES_ENV setting is invalid or if no API URL is configured for the
            environment.
        """
        env = self.get_environment()
        api_url = self.api_urls.get(env)
        if api_url is None:
            raise ValueError(
                f"No API URL configured for ANTARES environment '{env.value}'."
            )
        logger.debug(f"Using ANTARES API URL: {api_url} for environment: {env.value}")
        return api_url

    def get_url(self) -> str:
        """
        Get the ANTARES base URL from Django settings.

        Returns
        -------
        str
            The ANTARES base URL.

        Raises
        ------
        ValueError
            If the ANTARES_ENV setting is invalid or if no URL is configured for the
            environment.
        """
        env = self.get_environment()
        url = self.urls.get(env)
        if url is None:
            raise ValueError(
                f"No URL configured for ANTARES environment '{env.value}'."
            )
        logger.debug(f"Using ANTARES URL: {url} for environment: {env.value}")
        return url

    def get_timeout(self) -> int:
        """
        Get the ANTARES API timeout from Django settings or use the default.

        Returns
        -------
        int
            The ANTARES API timeout in seconds.
        """
        timeout = int(getattr(settings, "ANTARES_TIMEOUT", self.timeout))
        logger.debug(f"Using ANTARES timeout: {timeout} seconds")
        return timeout


ANTARESConfig = _ANTARESConfig()
