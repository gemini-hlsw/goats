"""Exception that displays for GOATS errors."""

__all__ = ["GOATSClickException"]

from typing import IO, Any

import click
from click._compat import get_text_stderr


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
