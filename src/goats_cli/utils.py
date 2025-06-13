"""Utilities for CLI to use."""

__all__ = [
    "display_message",
    "display_ok",
    "display_info",
    "display_failed",
    "display_warning",
    "port_in_use",
    "check_port_not_in_use",
    "parse_addrport",
    "open_browser",
    "wait_until_responsive",
]

import re
import socket
import time
import webbrowser

import click
import requests

from goats_cli.config import config
from goats_cli.exceptions import GOATSClickException


def display_message(
    message: str, show_goats_emoji: bool = True, color: str = "cyan"
) -> None:
    """Displays a styled message to the console.

    Parameters
    ----------
    message : `str`
        The message to display.
    show_goats_emoji : `bool`, optional
        If ``False``, the goats emoji is not prefixed to the message, by
        default ``True``.
    color : `str`
        The color to output the message in.

    """
    prefix = "🐐 " if show_goats_emoji else ""
    click.echo(click.style(f"{prefix}{message}", fg=color, bold=True))


def display_ok() -> None:
    """Display "OK" in green format."""
    time.sleep(0.5)
    click.echo(click.style(" OK", fg="green", bold=True))
    time.sleep(0.5)


def display_info(message: str, indent: int = 4) -> None:
    """Display a message with specified indentation.

    Parameters
    ----------
    message : `str`
        The message to be displayed.
    indent : `int`, optional
        The number of spaces for indentation, by default 4.

    """
    click.echo(f"{' ' * indent}{message}", nl=False)


def display_failed() -> None:
    """Display "FAILED" in red."""
    click.echo(click.style(" FAILED", fg="red", bold=True))


def display_warning(message: str, indent: int = 0) -> None:
    """Display a message in yellow format for warnings.

    Parameters
    ----------
    message : `str`
        The message to be displayed.
    indent : `int`, optional
        The number of spaces for indentation, by default 0.

    """
    click.echo(
        click.style(f"🐐 WARNING: {' ' * indent}{message}", fg="yellow", bold=True)
    )


def port_in_use(host, port) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


def check_port_not_in_use(service_name: str, host: str, port: int) -> None:
    """
    Displays logging messages, checks if the given host:port is in use,
    and raises GOATSClickException if so.
    """
    display_info(f"Checking {service_name} on {host}:{port}...")
    if port_in_use(host, port):
        display_failed()
        raise GOATSClickException(
            f"{service_name} instance already running on {host}:{port}. "
            "Please stop it before running GOATS again."
        )
    display_ok()


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

    display_warning(f"GOATS server did not respond after {attempts} attempts.")
    display_warning(
        f"Check if the server is running, then open your browser and go to: {url}"
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
    display_message(f"Opening GOATS at {url} in {browser_choice} browser.")
    try:
        if browser_choice == "default":
            webbrowser.open_new(url)
        else:
            browser = webbrowser.get(browser_choice)
            browser.open_new(url)
    except webbrowser.Error as e:
        display_warning(f"Failed to open browser '{browser_choice}': {str(e)}.")
        display_warning(f"Try opening a browser and navigate to: {url}")
