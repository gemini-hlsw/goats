import pytest
import requests
from unittest.mock import patch, MagicMock
from goats_cli.utils import (
    wait_until_responsive, open_browser, parse_addrport, display_message,display_ok,
    display_info,display_failed,display_warning, port_in_use, check_port_not_in_use
)
import webbrowser
import itertools
from goats_cli.config import config
import click
import socket
from goats_cli.exceptions import GOATSClickException


class TestPortChecks:
    """Test suite for checking port availability functions."""

    @patch("socket.socket")
    def test_port_in_use_true(self, mock_socket):
        """Test port_in_use returns True when port is in use."""
        mock_sock = MagicMock()
        # 0 = port in use.
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value.__enter__.return_value = mock_sock

        assert port_in_use("localhost", 8000) is True

    @patch("socket.socket")
    def test_port_in_use_false(self, mock_socket):
        """Test port_in_use returns False when port is not in use."""
        mock_sock = MagicMock()
        # 1 = port not in use.
        mock_sock.connect_ex.return_value = 1
        mock_socket.return_value.__enter__.return_value = mock_sock

        assert port_in_use("localhost", 8000) is False

    @patch("goats_cli.utils.port_in_use", return_value=True)
    @patch("goats_cli.utils.display_info")
    @patch("goats_cli.utils.display_failed")
    def test_check_port_not_in_use_raises_exception(
        self, mock_display_failed, mock_display_info, mock_port_in_use
    ):
        """Test check_port_not_in_use raises an exception if port is in use."""
        with pytest.raises(GOATSClickException, match="Django instance already running on localhost:8000."):
            check_port_not_in_use("Django", "localhost", 8000)

        mock_display_info.assert_called_once_with("Checking Django on localhost:8000...")
        mock_display_failed.assert_called_once()

    @patch("goats_cli.utils.port_in_use", return_value=False)
    @patch("goats_cli.utils.display_info")
    @patch("goats_cli.utils.display_ok")
    def test_check_port_not_in_use_passes(
        self, mock_display_ok, mock_display_info, mock_port_in_use
    ):
        """Test check_port_not_in_use passes when port is not in use."""
        check_port_not_in_use("Redis", "localhost", 6379)

        mock_display_info.assert_called_once_with("Checking Redis on localhost:6379...")
        mock_display_ok.assert_called_once()


@pytest.mark.parametrize("browser_choice, get_raises, expected_warning", [
    ("default", False, None),  # Default browser opens successfully.
    ("firefox", False, None),  # Specific browser opens successfully.
    ("chrome", True, "Failed to open browser 'chrome'"),  # Specified browser fails.
])
def test_open_browser(browser_choice, get_raises, expected_warning, capsys):
    url = "http://localhost:8000"
    with patch("webbrowser.get") as mock_get, patch("webbrowser.open_new") as mock_open:
        if get_raises:
            mock_get.side_effect = webbrowser.Error("Browser not found")

        open_browser(url, browser_choice)

        if browser_choice == "default":
            mock_open.assert_called_once_with(url)
        else:
            mock_get.assert_called_once_with(browser_choice)
            if not get_raises:
                mock_get.return_value.open_new.assert_called_once_with(url)

        if expected_warning:
            captured = capsys.readouterr()
            assert expected_warning in captured.out or captured.err


@pytest.mark.parametrize("side_effect, expected", [
    ([MagicMock(status_code=200)], True),  # Server is immediately responsive.
    ([requests.exceptions.ConnectionError()] * 2 + [MagicMock(status_code=200)], True),  # Fails 2 times, then works.
    (itertools.cycle([requests.exceptions.ConnectionError()]), False)  # Always fails.
])
def test_wait_until_responsive(side_effect, expected):
    url = "http://localhost:8000"
    with patch("requests.get", side_effect=side_effect) as mock_get:
        result = wait_until_responsive(url, timeout=2, retry_interval=0.1)
        assert result == expected



@pytest.mark.parametrize("addrport, expected", [
    ("localhost:8000", ("localhost", 8000)),  # Valid hostname.
    ("127.0.0.1:8080", ("127.0.0.1", 8080)),  # Valid IP address.
    ("0.0.0.0:5000", ("0.0.0.0", 5000)),  # Valid 0.0.0.0 binding.
    ("8000", (config.host, 8000)),  # Default host.
])
def test_parse_addrport_valid(addrport, expected, monkeypatch):
    assert parse_addrport(addrport) == expected

@pytest.mark.parametrize("addrport", [
    "localhost",  # Missing port.
    "localhost:",  # Empty port.
    "bad_address:xyz",  # Non-numeric port.
    ":8000",  # Missing host.
])
def test_parse_addrport_invalid(addrport):
    with pytest.raises(ValueError, match=f"Invalid addrport format: '{addrport}'"):
        parse_addrport(addrport)


class TestDisplayUtils:
    """Test suite for display utility functions."""

    @patch("click.echo")
    def test_display_message_with_emoji(self, mock_echo):
        """Test display_message with default emoji and color."""
        display_message("Test message")
        mock_echo.assert_called_once_with(click.style("🐐 Test message", fg="cyan", bold=True))

    @patch("click.echo")
    def test_display_message_without_emoji(self, mock_echo):
        """Test display_message without emoji."""
        display_message("Test message", show_goats_emoji=False)
        mock_echo.assert_called_once_with(click.style("Test message", fg="cyan", bold=True))

    @patch("click.echo")
    def test_display_message_custom_color(self, mock_echo):
        """Test display_message with a custom color."""
        display_message("Test message", color="red")
        mock_echo.assert_called_once_with(click.style("🐐 Test message", fg="red", bold=True))

    @patch("click.echo")
    def test_display_ok(self, mock_echo):
        """Test display_ok prints 'OK' in green."""
        with patch("time.sleep"):  # Skip sleep for speedup
            display_ok()
        mock_echo.assert_called_with(click.style(" OK", fg="green", bold=True))

    @patch("click.echo")
    def test_display_info(self, mock_echo):
        """Test display_info with default indentation."""
        display_info("Test info")
        mock_echo.assert_called_once_with("    Test info", nl=False)

    @patch("click.echo")
    def test_display_info_custom_indent(self, mock_echo):
        """Test display_info with custom indentation."""
        display_info("Test info", indent=6)
        mock_echo.assert_called_once_with("      Test info", nl=False)

    @patch("click.echo")
    def test_display_failed(self, mock_echo):
        """Test display_failed prints 'FAILED' in red."""
        display_failed()
        mock_echo.assert_called_once_with(click.style(" FAILED", fg="red", bold=True))

    @patch("click.echo")
    def test_display_warning(self, mock_echo):
        """Test display_warning prints a warning message in yellow."""
        display_warning("Test warning")
        mock_echo.assert_called_once_with(click.style("🐐 WARNING: Test warning", fg="yellow", bold=True))

    @patch("click.echo")
    def test_display_warning_with_indent(self, mock_echo):
        """Test display_warning with indentation."""
        display_warning("Test warning", indent=4)
        mock_echo.assert_called_once_with(click.style("🐐 WARNING:     Test warning", fg="yellow", bold=True))