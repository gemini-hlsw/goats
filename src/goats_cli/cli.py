"""
GOATS CLI main entry point.
"""

__all__ = ["cli"]

import typer

from goats_cli.commands import install, run

cli = typer.Typer(
    no_args_is_help=False,
    help="Command-line interface for the Gemini Observation and Analysis of Targets "
    "System (GOATS).\n\nProvides installation, configuration, and local runtime "
    "management of a complete GOATS environment.",
)

cli.add_typer(install.cli)
cli.add_typer(run.cli)


def main() -> None:
    """Main entry point for the GOATS CLI."""
    cli()


if __name__ == "__main__":
    main()
