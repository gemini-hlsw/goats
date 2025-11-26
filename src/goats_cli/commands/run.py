"""
GOATS CLI run command.
"""

import re
import subprocess
import time
from datetime import datetime, timezone
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable

import typer
from copier import run_recopy
from typing_extensions import Annotated

from goats_cli import output, utils
from goats_cli.commands.common import check_version, validate_project_structure
from goats_cli.config import config
from goats_cli.process import ProcessManager, ProcessName, StartResult

cli = typer.Typer()


class Browser(str, Enum):
    google_chrome = "google-chrome"
    firefox = "firefox"
    mozilla = "mozilla"
    chromium = "chromium"
    chrome = "chrome"
    chromium_browser = "chromium-browser"
    default = "default"


def _start_process(
    name: ProcessName,
    startup: dict[ProcessName, StartResult],
    starter: Callable[[], Any],
    manager: ProcessManager,
) -> None:
    """
    Start a GOATS subprocess and record its startup status.

    Parameters
    ----------
    name : ProcessName
        Name of the process being started.
    startup : dict[ProcessName, StartResult]
        Dictionary tracking startup results for all processes.
    starter : Callable[[], Any]
        Zero-argument function that launches the process when called.
        Typically created via `functools.partial`.
    manager : ProcessManager
        Process manager used to register running subprocesses.

    Raises
    ------
    Exception
        Any exception raised by the underlying process start is re-raised
        after updating startup results and printing a failure message.
    """
    try:
        proc = starter()
        manager.add_process(name, proc)
        startup[name] = StartResult(existed=True, started=True)
    except Exception as exc:
        startup[name] = StartResult(existed=True, started=False, error=str(exc))
        output.fail(f"Error starting {name.value}: {exc}")
        raise


def start_redis_server(addrport: str, disable_rdb: bool = True) -> subprocess.Popen:
    """Starts the Redis server.

    Parameters
    ----------
    addrport: str
        IP address and port to serve on.

    Returns
    -------
    subprocess.Popen
        The subprocess.
    """
    port = re.match(config.addrport_regex_pattern, addrport).group("port")
    cmd = ["redis-server", "--port", port]

    # Don't save to disk if disable_rdb is 'True'.
    if disable_rdb:
        cmd.extend(["--save", "''", "--appendonly", "no"])

    return subprocess.Popen(cmd, start_new_session=True)


def start_django_server(manage_file: Path, addrport: str) -> subprocess.Popen:
    """Starts the Django development server.

    Parameters
    ----------
    manage_file : Path
        Path to the GOATS manage file.
    addrport: str
        IP address and port to serve on.

    Returns
    -------
    subprocess.Popen
        The subprocess.
    """
    return subprocess.Popen(
        [str(manage_file), "runserver", addrport],
        start_new_session=True,
    )


def start_background_workers(manage_file: Path, workers: int) -> subprocess.Popen:
    """Starts the background workers.

    Parameters
    ----------
    manage_file : Path
        Path to the GOATS manage file.

    Returns
    -------
    subprocess.Popen
        The subprocess.
    """
    return subprocess.Popen(
        [
            str(manage_file),
            "rundramatiq",
            "--threads",
            str(workers),
            "--path",
            str(manage_file.parent),
            "--worker-shutdown-timeout",
            "1000",
        ],
        start_new_session=True,
    )


def start_task_scheduler(manage_file: Path) -> subprocess.Popen:
    """
    Start the APScheduler-based management command in the background via Popen.

    Parameters
    ----------
    manage_file : Path
        Path to the GOATS manage file.

    Returns
    -------
    subprocess.Popen
        The subprocess.
    """
    return subprocess.Popen(
        [str(manage_file), "run_scheduler"],
        start_new_session=True,
    )


@cli.command("run")
def run(
    project_name: Annotated[
        str,
        typer.Option(
            "--project-name",
            "-p",
            help=(
                "Name of the GOATS project to run. "
                "This is both the project directory and Django module name."
            ),
        ),
    ] = "GOATS",
    directory: Annotated[
        Path,
        typer.Option(
            "--directory",
            "-d",
            help=(
                "Parent directory where the GOATS project is located. "
                "Defaults to the current working directory."
            ),
        ),
    ] = Path.cwd(),
    workers: Annotated[
        int,
        typer.Option(
            "--workers",
            "-w",
            help="Number of Dramatiq workers to start for background tasks.",
        ),
    ] = 3,
    addrport: Annotated[
        str,
        typer.Option(
            "--addrport",
            "-a",
            callback=utils.validate_addrport,
            help=(
                "Address and port for Django. "
                "Formats: '8000', '0.0.0.0:8000', '192.168.1.5:8000'. "
                "Port-only binds to 127.0.0.1."
            ),
        ),
    ] = config.django_addrport,
    redis_addrport: Annotated[
        str,
        typer.Option(
            "--redis",
            "-r",
            callback=utils.validate_addrport,
            help=(
                "Address and port for Redis. "
                "Formats: '6379', 'localhost:6379', '192.168.1.5:6379'. "
                "Port-only binds to localhost."
            ),
        ),
    ] = config.redis_addrport,
    browser: Annotated[
        Browser,
        typer.Option(
            "--browser",
            "-b",
            help=(
                "Browser to launch GOATS with. Use 'default' to let the system decide."
            ),
        ),
    ] = Browser.default,
):
    """
    Run a local GOATS instance.

    This command launches the complete GOATS environment, including:
    the Redis server, the Django web server, Dramatiq background workers,
    and the APScheduler task scheduler. It also performs port checks and
    verifies that required components (such as Redis) are installed.

    Once servers are online, your browser is opened automatically to the GOATS
    web interface.
    """
    goats_version = utils.get_version()
    redis_host, redis_port = utils.parse_addrport(redis_addrport)
    django_host, django_port = utils.parse_addrport(addrport)
    start_time = datetime.now(timezone.utc).isoformat()

    run_msg = (
        "Launching a full local GOATS environment.\n\n"
        f"Started {start_time}.\n\n"
        "This command starts all required services:\n"
        "  [bold white]•[/] Redis\n"
        "  [bold white]•[/] Django web server\n"
        "  [bold white]•[/] Dramatiq background workers\n"
        "  [bold white]•[/] APScheduler task scheduler\n\n"
        "Once all services are ready, GOATS will automatically open in your browser."
        "\n\nUse Ctrl+C to stop GOATS and shut down all services."
    )

    output.panel(
        run_msg,
        title=f"Starting GOATS v{goats_version}",
        subtitle="🐐",
        border_style="green",
        expand=True,
    )
    utils.wait()

    check_version()

    project_path = directory.resolve() / project_name

    manage_file = validate_project_structure(project_path)

    output.section("Checking For GOATS Files Updates")
    with output.status("Checking and regenerating files if needed..."):
        utils.wait()
        try:
            # Add quiet=True to suppress copier output.
            run_recopy(
                dst_path=str(project_path),
                data={"goats_version": goats_version},
                overwrite=True,
                exclude=config.selective_exclude,
                skip_answered=True,
                skip_tasks=True,
            )
            output.success("Files are up to date.")
        except Exception as exc:
            output.fail(f"Failed to update files: {exc}")
            raise typer.Exit(1)

    output.section("Validating Environment")
    with output.status("Checking Redis installation..."):
        try:
            subprocess.run(
                ["redis-server", "--version"],
                capture_output=True,
                check=True,
                text=True,
            )
            output.success("Redis installed")
        except FileNotFoundError:
            output.fail("Redis is not installed on this system.")
            raise typer.Exit(1)

    with output.status("Checking for host/port conflicts..."):
        utils.check_port_not_in_use("Redis", redis_host, redis_port)
        utils.check_port_not_in_use("Django", django_host, django_port)

    output.section("Launching GOATS Processes")
    utils.wait()

    process_manager = ProcessManager()
    startup_results: dict[ProcessName, StartResult] = {}
    try:
        # Start all subprocesses.
        _start_process(
            ProcessName.REDIS,
            startup_results,
            partial(start_redis_server, redis_addrport),
            process_manager,
        )

        _start_process(
            ProcessName.DJANGO,
            startup_results,
            partial(start_django_server, manage_file, addrport),
            process_manager,
        )

        _start_process(
            ProcessName.BACKGROUND_WORKERS,
            startup_results,
            partial(start_background_workers, manage_file, workers),
            process_manager,
        )

        _start_process(
            ProcessName.TASK_SCHEDULER,
            startup_results,
            partial(start_task_scheduler, manage_file),
            process_manager,
        )

        url = f"http://{django_host}:{django_port}"

        if utils.wait_until_responsive(url):
            utils.open_browser(url, browser.value)

        # Keep running until interrupted.
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        output.space()
        output.warning("Shutdown requested (Ctrl+C).")

    except Exception:
        output.fail("GOATS failed to start properly.")
        output.print_exception()

    finally:
        # Generate startup summary if missing any results.
        for process_name in ProcessName.startup_order():
            if process_name not in startup_results:
                startup_results[process_name] = StartResult(False, False)

        stop_results = process_manager.stop_all()
        output.section("GOATS Startup Summary")
        output.start_summary_table(startup_results)

        output.section("GOATS Shutdown Summary")
        output.stop_summary_table(stop_results)

        output.success("GOATS has shut down. Goodbye!")
