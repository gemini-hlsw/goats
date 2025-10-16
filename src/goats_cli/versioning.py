from importlib.metadata import version as get_version

import click
import requests
from packaging.version import InvalidVersion, Version

import goats_cli.utils as utils
from goats_cli.exceptions import GOATSClickException

UPDATE_DOC_URL = "https://goats.readthedocs.io/en/stable/update.html"
CHANNELDATA_URL = "https://gemini-hlsw.github.io/goats-infra/conda/channeldata.json"


def check_version() -> bool:
    """
    Check whether GOATS is outdated.

    Returns
    -------
    bool
        True if an update is available (installed < latest), otherwise False.

    Raises
    ------
    GOATSClickException
        If the latest version cannot be resolved or version strings are invalid.
    """
    utils.display_message("Checking for updates:")

    utils.display_info("Resolving installed version... ")
    current = get_version("goats").strip()
    utils.display_ok()

    utils.display_info("Querying latest version from channel... ")
    try:
        latest = _get_latest_version().strip()
        utils.display_ok()
    except GOATSClickException:
        utils.display_failed()
        raise

    try:
        if Version(current) < Version(latest):
            utils.display_warning(
                f"A new version of GOATS is available: {latest} (current: {current})"
            )
            utils.display_info(
                f"➤ Visit {UPDATE_DOC_URL} for update instructions\n",
            )
            utils.display_info(
                "Press Enter to continue, or Ctrl+C to cancel...",
            )
            try:
                click.prompt("", default="", show_default=False, prompt_suffix="")
            except (KeyboardInterrupt, EOFError):
                raise click.Abort()
            return True

    except InvalidVersion as error:
        utils.display_failed()
        raise GOATSClickException(f"Invalid version string: {error}") from error

    utils.display_message("Nothing to do, you are up to date.\n")
    return False


def _get_latest_version() -> str:
    """
    Return the latest GOATS version string from the GOATS Conda channel.

    This function downloads the channel metadata (``channeldata.json``) and extracts
    the version of the ``goats`` package.

    Returns
    -------
    str
        Latest version string (e.g., ``"1.2.3"``).

    Raises
    ------
    GOATSClickException
        If there is a network/HTTP error or the response payload cannot be parsed.

    Notes
    -----
    Source URL
        ``https://gemini-hlsw.github.io/goats-infra/conda/channeldata.json``

    """
    try:
        resp = requests.get(
            CHANNELDATA_URL,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["packages"]["goats"]["version"]
    except requests.RequestException as error:
        raise GOATSClickException(f"Failed to fetch latest version info: {error}")
    except (KeyError, ValueError) as error:
        raise GOATSClickException(
            f"Malformed channel metadata while obtaining latest version: {error}"
        )
