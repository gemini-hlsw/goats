"""CLI for installing and running GOATS."""

__all__ = ["cli"]
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import IO, Any

import click
import requests
from click._compat import get_text_stderr

from goats_cli.modify_settings import modify_settings
from goats_cli.process_manager import ProcessManager
from goats_cli.utils import (
    display_failed,
    display_info,
    display_message,
    display_ok,
    display_warning,
)

REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
REDIS_ADDRPORT: str = f"{REDIS_HOST}:{REDIS_PORT}"
REGEX_PATTERN = r"^(?:(?P<host>[^:]+):)?(?P<port>[0-9]+)$"
DEFAULT_HOST: str = "localhost"
DEFAULT_PORT: int = 8000
DEFAULT_ADDRPORT: str = f"{DEFAULT_HOST}:{DEFAULT_PORT}"


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
    pattern = re.compile(REGEX_PATTERN)
    match = pattern.match(addrport)
    if not match:
        raise ValueError(f"Invalid addrport format: '{addrport}'")

    host = match.group("host") or DEFAULT_HOST
    port = int(match.group("port"))
    return host, port


class GOATSClickException(click.ClickException):
    """An extension of ClickException to show a goat emoji with the message."""

    def show(self, file: IO[Any] | None = None) -> None:
        """Display the error message prefixed with a goat emoji.

        If a file object is passed, it writes the message to the file,
        otherwise, it writes the message to standard error.

        Parameters
        ----------
        file : `IO[Any] | None`, optional
            The file object to write the message to, by default ``None``.

        """
        if file is None:
            file = get_text_stderr()

        click.echo(
            click.style(f"🐐 Error: {self.format_message()}", fg="red", bold=True),
            file=file,
        )


def validate_addrport(ctx, param, value):
    """Validate IP address and port."""
    if not re.match(REGEX_PATTERN, value):
        raise click.BadParameter(
            "The address and port must be in format 'HOST:PORT' or 'PORT'.",
        )
    return value


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Gemini Observation and Analysis of Targets System (GOATS).

    You can run each subcommand with its own options and arguments. For
    details on a specific command, type 'goats COMMAND --help'.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@click.command(help=("Installs GOATS and configures Redis server."))
@click.option(
    "-p",
    "--project-name",
    default="GOATS",
    type=str,
    help="Specify a custom project name. Default is 'GOATS'.",
)
@click.option(
    "-d",
    "--directory",
    default=Path.cwd(),
    type=Path,
    help=(
        "Specify the parent directory where GOATS will be installed. "
        "Default is the current directory."
    ),
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite the existing project, if it exists. Default is False.",
)
@click.option(
    "-m",
    "--media-dir",
    type=Path,
    help="Path for saving downloaded media.",
    default=None,
)
@click.option(
    "--redis-addrport",
    default=REDIS_ADDRPORT,
    type=str,
    help=(
        "Specify the Redis server IP address and port number. "
        "Examples: '6379', 'localhost:6379', '192.168.1.5:6379'. "
        "Providing only a port number (e.g., '6379') binds to localhost."
    ),
    callback=validate_addrport,
)
def install(
    project_name: str,
    directory: Path,
    overwrite: bool,
    media_dir: Path | None,
    redis_addrport: str,
) -> None:
    """Installs GOATS with a specified or default name in a specified or
    default directory and configures Redis server.

    Parameters
    ----------
    project_name : `str`
        The name of the project to be created.
    directory : `Path`
        The directory where the project will be created.
    overwrite : `bool`
        Whether to overwrite the existing project if it exists, default is
        `False`.
    media_dir : `Path | None`
        The path to save media files.
    redis_addrport : `str`
        The host and port Redis is served on.

    Raises
    ------
    GOATSClickException
        Raised if GOATS installation already exists and overwrite disabled.
    GOATSClickException
        Raised if the 'subprocess' calls fail.
    GOATSClickException
        Raised if the 'media_dir' path is not writable.

    """
    project_path = directory.resolve() / project_name

    # If directory and project exist, ask to remove.
    if (project_path).is_dir():
        if not overwrite:
            raise GOATSClickException(
                f"'{project_path.absolute()}' already exists. Use the "
                "'--overwrite' option to overwrite it.",
            )
        shutil.rmtree(project_path)

    # If directory is provided, make sure it exists.
    directory.mkdir(parents=True, exist_ok=True)

    try:
        # Run the startproject command in the specified directory.
        subprocess.run(
            ["django-admin", "startproject", project_name],
            cwd=directory,
            check=True,
        )

        # Get the path for the 'settings.py' file.
        settings_file = project_path / project_name / "settings.py"

        # Add the TOM Toolkit plugin.
        modify_settings(settings_file, add_goats=True)
        # Get the path for the 'manage.py' file.
        manage_file = project_path / "manage.py"

        # Setup the TOM Toolkit.
        goats_setup_command = [
            f"{manage_file}",
            "goats_setup",
            "--redis-addrport",
            f"{redis_addrport}",
        ]
        # Change the MEDIA_ROOT if provided.
        if media_dir:
            resolved_media_dir = media_dir.resolve()
            if resolved_media_dir.exists():
                display_warning(
                    "Media root directory already exists, proceeding but existing "
                    "data might conflict."
                )
            goats_setup_command.extend(["--media-dir", f"{resolved_media_dir}"])

        subprocess.run(goats_setup_command, check=True)

        # Migrate the webpage.
        display_message("Wrapping up:", show_goats_emoji=False)
        display_info("Running final migrations... ")
        subprocess.run(
            [f"{manage_file}", "makemigrations"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        subprocess.run(
            [f"{manage_file}", "migrate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        display_ok()

        display_message("GOATS installed!", color="green")

    except subprocess.CalledProcessError as error:
        cmd_str = " ".join(error.cmd)
        raise GOATSClickException(
            f"An error occurred while running the command: '{cmd_str}'. Exit status:"
            f" {error.returncode}."
        )

    except Exception as error:
        raise GOATSClickException(str(error))


@click.command(help=("Starts the webserver, Redis server, and workers for GOATS."))
@click.option(
    "-p",
    "--project-name",
    default="GOATS",
    type=str,
    help="Specify a custom project name. Default is 'GOATS'.",
)
@click.option(
    "-d",
    "--directory",
    default=Path.cwd(),
    type=Path,
    help=(
        "Specify the parent directory where GOATS is installed. "
        "Default is the current directory."
    ),
)
@click.option(
    "-w",
    "--workers",
    default=3,
    type=int,
    help="Number of workers to spawn for background tasks.",
)
@click.option(
    "--addrport",
    default=DEFAULT_ADDRPORT,
    type=str,
    help=(
        "Specify the IP address and port number to serve GOATS. "
        "Examples: '8000', '0.0.0.0:8000', '192.168.1.5:8000'. "
        "Providing only a port number (e.g., '8000') binds to 127.0.0.1."
    ),
    callback=validate_addrport,
)
@click.option(
    "--redis-addrport",
    default=REDIS_ADDRPORT,
    type=str,
    help=(
        "Specify the Redis server IP address and port number. "
        "Examples: '6379', 'localhost:6379', '192.168.1.5:6379'. "
        "Providing only a port number (e.g., '6379') binds to localhost."
    ),
    callback=validate_addrport,
)
@click.option(
    "-b",
    "--browser",
    type=click.Choice(
        [
            "google-chrome",
            "firefox",
            "mozilla",
            "chromium",
            "chrome",
            "chromium-browser",
            "default",
        ],
        case_sensitive=False,
    ),
    default="default",
    help="Specify the browser to open GOATS in (chrome, firefox, or default).",
)
def run(
    project_name: str,
    directory: Path,
    workers: int,
    addrport: str,
    redis_addrport: str,
    browser: str,
) -> None:
    """Starts the webserver, Redis server, and workers for GOATS.

    Parameters
    ----------
    project_name : `str`
        The name of the project to be started.
    directory : `Path`
        The directory where the project is installed.
    workers : `int`
        The number of workers to spawn for background tasks.
    addrport : `str`
        The host and port to serve GOATS on.
    redis_addrport : `str`
        The host and port Redis is served on.
    browser: `str`
        The browser to open GOATS with.

    Raises
    ------
    GOATSClickException
        Raised if the 'manage.py' file for the project does not exist.
    GOATSClickException
        Raised if the 'subprocess' calls fail.

    """
    display_message("Serving GOATS.\n")
    display_message("Finding GOATS and Redis installation:", show_goats_emoji=False)
    display_info("Verifying 'manage.py' exists for GOATS...")
    project_path = directory / project_name
    # Get the path for the 'manage.py' file.
    manage_file = project_path / "manage.py"
    if not manage_file.is_file():
        display_failed()
        raise GOATSClickException(
            f"The 'manage.py' file for the project '{project_name}' does not exist at"
            f" '{manage_file.absolute()}'."
        )
    display_ok()
    display_info("Verifying Redis installed...")
    try:
        subprocess.run(
            ["redis-server", "--version"],
            check=True,
            text=True,
            capture_output=True,
        )
        display_ok()
    except FileNotFoundError:
        display_failed()
        raise GOATSClickException(
            "An error occurred verifying Redis. Is Redis installed?",
        )

    display_message(
        "Starting Redis, GOATS and background workers:",
        show_goats_emoji=False,
    )
    display_message(
        "---------------------------------------------",
        show_goats_emoji=False,
    )
    time.sleep(2)

    try:
        process_manager = ProcessManager()

        # Start the Redis server.
        process_manager.add_process("redis", start_redis_server(redis_addrport))

        # Start Django server.
        process_manager.add_process(
            "django", start_django_server(manage_file, addrport)
        )

        # Start the background consumer.
        process_manager.add_process(
            "background_workers",
            start_background_workers(manage_file, workers=workers),
        )

        # Open the browser.
        host, port = parse_addrport(addrport)
        url = f"http://{host}:{port}"
        if wait_until_responsive(url):
            # Build the url and open it.
            open_browser(url, browser)

        while True:
            time.sleep(0.1)

    finally:
        process_manager.stop_all()


def start_redis_server(addrport: str, disable_rdb: bool = True) -> subprocess.Popen:
    """Starts the Redis server.

    Parameters
    ----------
    addrport: `str`
        IP address and port to serve on.

    Returns
    -------
    `subprocess.Popen`
        The subprocess.

    Raises
    ------
    GOATSClickException
        Raised if issue starting Redis server.

    """
    display_message("Starting redis database.")
    pattern = re.compile(REGEX_PATTERN)
    match = pattern.match(addrport)
    port = match.group("port")
    cmd = ["redis-server", "--port", f"{port}"]

    # Don't save snapshot if True.
    if disable_rdb:
        cmd.extend(["--save", "''", "--appendonly", "no"])
    try:
        redis_process = subprocess.Popen(cmd, start_new_session=True)
    except subprocess.CalledProcessError as error:
        raise GOATSClickException(
            f"Error running Redis server: '{error.cmd}'. "
            f"Exit status: {error.returncode}.",
        )
    return redis_process


def start_django_server(manage_file: Path, addrport: str) -> subprocess.Popen:
    """Starts the Django development server.

    Parameters
    ----------
    manage_file : `Path`
        Path to the GOATS manage file.
    addrport: `str`
        IP address and port to serve on.

    Returns
    -------
    `subprocess.Popen`
        The subprocess.

    Raises
    ------
    GOATSClickException
        Raised if issue starting Django server.

    """
    display_message("Starting django server.")
    try:
        django_process = subprocess.Popen(
            [f"{manage_file}", "runserver", addrport],
            start_new_session=True,
        )
    except subprocess.CalledProcessError as error:
        raise GOATSClickException(
            f"Error running Django server: '{error.cmd}'. "
            f"Exit status: {error.returncode}.",
        )
    return django_process


def start_background_workers(manage_file: Path, workers: int) -> subprocess.Popen:
    """Starts the background workers.

    Parameters
    ----------
    manage_file : `Path`
        Path to the GOATS manage file.

    Returns
    -------
    `subprocess.Popen`
        The subprocess.

    Raises
    ------
    GOATSClickException
        Raised if issue starting background workers.

    """
    display_message("Starting background workers.")
    try:
        background_workers_process = subprocess.Popen(
            [
                f"{manage_file}",
                "rundramatiq",
                "--threads",
                f"{workers}",
                "--path",
                f"{manage_file.parent}",
                "--worker-shutdown-timeout",
                "1000",
            ],
            start_new_session=True,
        )
    except subprocess.CalledProcessError as error:
        raise GOATSClickException(
            f"Error running background consumer: '{error.cmd}'. "
            f"Exit status: {error.returncode}."
        )
    return background_workers_process


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


cli.add_command(install)
cli.add_command(run)
