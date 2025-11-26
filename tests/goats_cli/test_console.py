from rich.console import Console

from goats_cli.console import console, error_console


def test_console_instance():
    """Test that the `console` instance is correctly created."""
    assert isinstance(console, Console)
    assert console._highlight is False
    assert console.stderr is False


def test_error_console_instance():
    """Test that the `error_console` instance is correctly created."""
    assert isinstance(error_console, Console)
    assert error_console._highlight is False
    assert error_console.stderr is True
