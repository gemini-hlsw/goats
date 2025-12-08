"""
GOATS CLI install command.
"""

import os
import shutil
import subprocess
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

import typer
from copier import run_copy
from django.core.management.utils import get_random_secret_key
from typing_extensions import Annotated

from goats_cli import output, utils
from goats_cli.commands.common import (
    check_version,
    run_migrations,
    validate_project_structure,
)
from goats_cli.config import config

cli = typer.Typer()


def copy_goats_files(
    project_path: Path, data: dict[str, Any], quiet: bool = True
) -> None:
    """
    Copy GOATS template files to target project path using Copier.

    Parameters
    ----------
    project_path : Path
        Path where the GOATS project should be created.
    data : dict[str, Any]
        Context data for Copier templates.
    quiet : bool, default=True
        Whether to suppress Copier output. By default, ``True``.

    Raises
    ------
    typer.Exit
        If copying the template fails.
    """
    with output.status("Copying GOATS template..."):
        try:
            run_copy(
                src_path=str(files("goats_cli").joinpath("goats_template")),
                dst_path=str(project_path),
                data=data,
                defaults=True,
                quiet=quiet,
            )
            utils.wait()
        except Exception as e:
            output.fail(f"Error copying template: {e}")
            output.print_exception()
            raise typer.Exit(1)

    output.success("GOATS template copied.")


@cli.command("install")
def install(
    project_name: Annotated[
        str,
        typer.Option(
            "--project-name",
            "-p",
            help=(
                "Name of the Django project to create. "
                "This becomes both the folder name and the internal project module."
            ),
        ),
    ] = "GOATS",
    directory: Annotated[
        Path,
        typer.Option(
            "--directory",
            "-d",
            help=(
                "Directory in which the GOATS project will be installed. "
                "Defaults to the current working directory."
            ),
        ),
    ] = Path.cwd(),
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help=(
                "Replace the target project directory if it already exists. "
                "Without this flag, installation will abort if a project is found."
            ),
        ),
    ] = False,
    media_dir: Annotated[
        Path | None,
        typer.Option(
            "--media-dir",
            "-m",
            help=(
                "Path where GOATS should store media files. "
                "If omitted, the project uses its internal default media directory."
            ),
        ),
    ] = None,
    redis_addrport: Annotated[
        str,
        typer.Option(
            "--redis",
            "-r",
            callback=utils.validate_addrport,
            help=(
                "Address and port for Redis. "
                "Accepted formats: 'PORT' or 'HOST:PORT'. "
                "Examples: '6379', 'localhost:6379', '192.168.1.10:6379'."
            ),
        ),
    ] = config.redis_addrport,
    headless_superuser: Annotated[
        bool,
        typer.Option(
            "--headless-superuser",
            help=(
                "Create a Django superuser in non-interactive mode using the "
                "default --su-username and --su-email unless overridden. "
                "Requires DJANGO_SUPERUSER_PASSWORD env variable to be set."
            ),
        ),
    ] = False,
    su_username: Annotated[
        str,
        typer.Option(
            "--su-username",
            help=(
                "Username for headless superuser creation. Only used when "
                "--headless-superuser is provided."
            ),
        ),
    ] = config.su_username,
    su_email: Annotated[
        str,
        typer.Option(
            "--su-email",
            help=(
                "Email for headless superuser creation. Only used when "
                "--headless-superuser is provided."
            ),
        ),
    ] = config.su_email,
):
    """
    Install a new GOATS project in the chosen directory.

    This command creates a fully configured Django project, initializes Redis
    connection settings, applies initial database migrations, and optionally sets
    up a media storage directory. If the target location already contains a project,
    you may overwrite it with the --overwrite flag.

    After installation, a superuser account is created required user input unless
    running in CI mode.
    """
    goats_version = utils.get_version()
    redis_host, redis_port = utils.parse_addrport(redis_addrport)
    create_date = datetime.now(timezone.utc).isoformat()

    install_msg = (
        "Welcome to the GOATS installer.\n\n"
        "GOATS is a browser-based interface for time-domain and multi-messenger "
        "follow-up, automating the workflow from target selection and triggering to "
        "data retrieval, reduction, and analysis.\n"
        "It is a fully assembled Target and Observation Manager built on the TOM "
        "Toolkit, providing a ready-to-use system with no custom development required."
        "\n\n"
        "Installation will complete in a few steps."
    )

    output.panel(
        install_msg,
        title=f"GOATS v{goats_version} Installation",
        subtitle="🐐",
        border_style="green",
        expand=True,
    )
    utils.wait()

    check_version()

    output.section("Preparing Installation")

    # Get paths.
    parent_dir = directory.resolve()
    project_path = parent_dir / project_name

    info_table_data = {
        "Version": goats_version,
        "Parent directory": str(parent_dir),
        "Project directory": str(project_path),
        "Redis address": redis_addrport,
        "Installation date": create_date,
    }

    # Include media directory in info table if applicable.
    if media_dir:
        info_table_data["Media directory"] = str(media_dir.resolve())

    # If the project directory exists and overwrite is not allowed
    if project_path.exists() and not overwrite:
        output.fail(
            f"A GOATS project already exists at: {project_path}\n"
            "  To replace it, re-run with --overwrite."
        )
        raise typer.Exit(1)

    # Overwrite mode
    if project_path.exists() and overwrite:
        output.warning(
            f"A GOATS project already exists at: {project_path}\n"
            "  It will be completely removed before creating a new installation."
        )
        with output.status("Removing existing GOATS installation..."):
            utils.wait()
            shutil.rmtree(project_path)
        output.success("Previous GOATS installation removed.")

    output.success("Installation preparation complete.")

    output.section("Creating GOATS Project")

    # Create project directory.
    directory.mkdir(parents=True, exist_ok=True)

    # Template context for copier.
    secret_key = get_random_secret_key()

    data = {
        "project_name": project_name,
        "secret_key": secret_key,
        "create_date": create_date,
        "goats_version": goats_version,
        "redis_host": redis_host,
        "redis_port": redis_port,
    }

    if media_dir:
        resolved_media_dir = media_dir.resolve()
        if resolved_media_dir.exists():
            output.warning(
                "Media root directory already exists, proceeding but existing "
                "data might conflict."
            )
        output.info(f"Using custom media directory: {resolved_media_dir}")
        resolved_media_dir.mkdir(parents=True, exist_ok=True)
        data["media_root"] = str(resolved_media_dir)

    copy_goats_files(project_path, data)

    manage_file = validate_project_structure(project_path)

    run_migrations(manage_file)

    output.section(f"Creating Superuser {'(Headless)' if headless_superuser else ''}")
    env = os.environ.copy()
    superuser_cmd = [str(manage_file), "createsuperuser"]

    if headless_superuser:
        # Validate required inputs.
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            output.fail(
                "Environment variable DJANGO_SUPERUSER_PASSWORD is required "
                "when using --headless-superuser."
            )
            raise typer.Exit(1)

        if not su_username:
            output.fail(
                "You must provide --su-username when using --headless-superuser."
            )
            raise typer.Exit(1)
        if not su_email:
            output.fail("You must provide --su-email when using --headless-superuser.")
            raise typer.Exit(1)

        output.info_table(
            {"Username": su_username, "Email": su_email, "Password": "********"}
        )
        # Copy password to env for subprocess.
        env["DJANGO_SUPERUSER_PASSWORD"] = password

        superuser_cmd.extend(
            [
                "--noinput",
                "--username",
                su_username,
                "--email",
                su_email,
            ]
        )

    # Set GOATS_ENV to 'cli' to disable logging.
    env["GOATS_ENV"] = "cli"
    output.procedure("Launching Django superuser creation")
    output.space()
    try:
        subprocess.run(
            superuser_cmd,
            check=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        output.fail(f"Superuser creation failed: {exc}")
        output.print_exception()
        raise typer.Exit(1)

    output.space()
    output.success("Done creating superuser.")

    output.section("Installation Complete")
    output.info_table(info_table_data)
    output.procedure("Next steps")
    output.procedure_steps(
        [f"goats run -d {project_path.parent} -p {project_path.name}"]
    )
    output.space()
    output.success("GOATS installed successfully!")
