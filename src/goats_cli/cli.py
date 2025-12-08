"""
GOATS CLI main entry point.
"""

__all__ = ["cli"]

import typer
from typing_extensions import Annotated

from goats_cli.commands import install, run
from goats_common import VersionChecker

__version__ = VersionChecker().current_version

cli = typer.Typer(
    no_args_is_help=False,
    help="Command-line interface for the Gemini Observation and Analysis of Targets "
    "System (GOATS).\n\nProvides installation, configuration, and local runtime "
    "management of a complete GOATS environment.",
)


def version_callback(value: bool):
    if value:
        print(f"{__version__}")
        raise typer.Exit()


@cli.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the GOATS CLI version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
):
    """Main entry point callback for the GOATS CLI."""
    pass


cli.add_typer(install.cli)
cli.add_typer(run.cli)


def main() -> None:
    """Main entry point for the GOATS CLI."""
    cli()


if __name__ == "__main__":
    main()
