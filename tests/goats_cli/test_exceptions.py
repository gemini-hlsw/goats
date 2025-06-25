from unittest.mock import MagicMock, patch

import click
from click._compat import get_text_stderr

from goats_cli.exceptions import GOATSClickException


def test_goats_click_exception_message():
    """Test that GOATSClickException stores and formats the message correctly."""
    exception = GOATSClickException("Something went wrong")
    assert exception.format_message() == "Something went wrong"


@patch("click.echo")
def test_goats_click_exception_show(mock_echo):
    """Test that GOATSClickException displays the error message correctly."""
    exception = GOATSClickException("Something went wrong")

    # Mock a file-like object.
    mock_file = MagicMock()

    # Call the show method.
    exception.show(file=mock_file)

    # Verify that click.echo was called with the expected formatted message.
    mock_echo.assert_called_once_with(
        click.style("🐐 Error: Something went wrong", fg="red", bold=True),
        file=mock_file,
    )


@patch("click.echo")
def test_goats_click_exception_show_default_file(mock_echo):
    """Test that GOATSClickException defaults to stderr when no file is provided."""

    exception = GOATSClickException("Something went wrong")

    # Call the show method without passing a file.
    exception.show()

    # Verify that click.echo was called with the expected formatted message.
    mock_echo.assert_called_once_with(
        click.style("🐐 Error: Something went wrong", fg="red", bold=True),
        file=get_text_stderr(),
    )
