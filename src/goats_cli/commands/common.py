"""
GOATS CLI common command utilities.
"""

__all__ = ["validate_project_structure", "run_migrations", "check_version"]

import subprocess
from pathlib import Path

import typer

from goats_cli import output
from goats_cli.config import config
from goats_common.version_checker import VersionChecker


def validate_project_structure(project_path: Path) -> Path:
    """
    Eventually validate the project structure but for now just check manage.py.

    Parameters
    ----------
    project_path : Path
        Path to the GOATS project.

    Returns
    -------
    Path
        Path to the manage.py file.

    Raises
    ------
    typer.Exit
        If manage.py is not found.
    """
    output.section("Validating GOATS Project Structure")
    with output.status("Checking project files..."):
        manage_file = project_path / "manage.py"
        if not manage_file.is_file():
            output.fail(
                "Could not validate GOATS, please check the installation at "
                f"{project_path}."
            )
            raise typer.Exit(1)
        # TODO: Evenything else could just be a warning if manage.py exists.

    output.success("GOATS project structure validated.")
    return manage_file


def run_migrations(manage_file: Path) -> None:
    """Run Django migrations with nice Rich output."""
    output.section("Database Migrations")
    with output.status("Applying database migrations..."):
        try:
            process = subprocess.run(
                [str(manage_file), "migrate"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            output.fail(f"Failed to apply migrations: {exc}")
            output.print_exception()
            raise typer.Exit(1)
    if process.stdout.strip():
        output.subprocess_info_and_padding(
            "Migrations output", process.stdout.strip("\n")
        )

    output.success("Database migrations applied")


def check_version() -> None:
    """Check GOATS version and notify if outdated."""
    output.section("Checking GOATS Version")

    checker = VersionChecker()

    is_outdated = checker.is_outdated

    if is_outdated:
        output.warning(
            f"New version available: {checker.latest_version} "
            f"(current: {checker.current_version})"
        )
        output.info(
            "GOATS interacts with GPP, GOA, and TNS — outdated versions may fail "
            "unexpectedly."
        )
        output.space()
        output.procedure("Update instructions")
        output.procedure_steps(["Stop GOATS", "Run: conda update goats"])
        output.space()
        output.dim_info(f"See: {config.update_doc_url}")
        output.space()
        if not output.confirm_prompt("Continue anyway?"):
            raise typer.Abort()
    elif checker.is_outdated is None:
        output.warning("Could not determine GOATS version status.\n  Continuing...")
    else:
        output.success("GOATS is up to date.")
