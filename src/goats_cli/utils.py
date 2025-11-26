"""
GOATS CLI utility functions.
"""

__all__ = [
    "port_in_use",
    "check_port_not_in_use",
    "wait_until_responsive",
    "open_browser",
    "parse_addrport",
    "get_version",
    "wait",
    "validate_addrport",
]

import re
import socket
import time
import webbrowser

import requests
import typer

from goats_cli import output
from goats_cli.config import config
from goats_common.version_checker import VersionChecker


def port_in_use(host, port) -> bool:
    """
    Checks if a given port on a host is in use.

    Parameters
    ----------
    host : str
        Hostname or IP address.
    port : int
        Port number.

    Returns
    -------
    bool
        ``True`` if the port is in use, ``False`` otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


def check_port_not_in_use(service_name: str, host: str, port: int) -> None:
    """
    Displays logging messages, checks if the given host:port is in use,
    and raises typer.Exit if so.

    Parameters
    ----------
    service_name : str
        Name of the service being checked.
    host : str
        Hostname or IP address.
    port : int
        Port number.

    Raises
    ------
    typer.Exit
        If the port and host is already in use.
    """
    if port_in_use(host, port):
        output.fail(f"{service_name} on {host}:{port} is already in use.")
        raise typer.Exit(1)

    output.success(f"{service_name} on {host}:{port} is available.")


def wait_until_responsive(
    url: str, timeout: int = 30, retry_interval: float = 1.0
) -> bool:
    """Waits until the server responds with a valid HTTP status.

    Parameters
    ----------
    url : `str`
        The URL of the server to check.
    timeout : `int`
        Maximum time in seconds to wait for the server to respond.
    retry_interval : `float`
        Time in seconds to wait between retries (default: 1s).

    Returns
    -------
    `bool`
        `True` if the server is responsive, `False` if the timeout is reached.
    """
    start_time = time.time()
    attempts = 0  # Track how many times we retry

    while time.time() - start_time < timeout:
        attempts += 1
        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                return True
        except Exception:
            time.sleep(retry_interval)

    output.warning(
        f"GOATS server did not respond after {attempts} attempts.\n"
        f"  Check if the server is running, then open your browser and go to: {url}"
    )
    return False


def open_browser(url: str, browser_choice: str) -> None:
    """Opens the specified browser or defaults to the system browser.

    Parameters
    ----------
    url : `str`
        The URL to open in the browser.
    browser_choice : `str`
        The browser choice.
    """
    output.info(f"Opening GOATS at {url} in {browser_choice} browser.")
    try:
        if browser_choice == "default":
            webbrowser.open_new(url)
        else:
            browser = webbrowser.get(browser_choice)
            browser.open_new(url)
    except webbrowser.Error as e:
        output.warning(
            f"Failed to open browser '{browser_choice}': {str(e)}\n"
            f"  Try opening a browser and navigate to: {url}"
        )


def parse_addrport(addrport: str) -> tuple[str, int]:
    """Parses an address and port string into host and port components.

    Parameters
    ----------
    addrport : `str`
        The address and port string, e.g., "localhost:8000" or "8000".

    Returns
    -------
    `tuple[str, int]`
        A tuple of (host, port), where host is a string and port is an integer.

    Raises
    ------
    ValueError
        If the input does not match the expected format.
    """
    pattern = re.compile(config.addrport_regex_pattern)
    match = pattern.match(addrport)
    if not match:
        raise ValueError(f"Invalid addrport format: '{addrport}'")

    host = match.group("host") or config.host
    port = int(match.group("port"))
    return host, port


def get_version() -> str | None:
    """
    Get the current version of GOATS.

    Returns
    -------
    str | None
        The current version of GOATS or ``None`` if it cannot be determined.
    """
    checker = VersionChecker()
    return checker.current_version


def wait(seconds: float = 1.5) -> None:
    """Pause execution for a specified number of seconds.

    Parameters
    ----------
    seconds : `float`, optional
        The number of seconds to wait, by default 1.5 seconds.

    """
    time.sleep(seconds)


def validate_addrport(value: str) -> str:
    """Typer callback — validate 'HOST:PORT' or 'PORT'."""
    if not re.match(config.addrport_regex_pattern, value):
        raise typer.BadParameter(
            "Expected 'PORT' or 'HOST:PORT'. Example: 8000 or 0.0.0.0:8000"
        )
    return value
