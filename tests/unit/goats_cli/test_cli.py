import click.testing
import pytest
from goats_cli import cli
import requests
from unittest.mock import patch, MagicMock
from goats_cli.cli import wait_until_responsive, open_browser, parse_addrport, DEFAULT_HOST
import webbrowser


@pytest.fixture()
def runner():
    return click.testing.CliRunner()


def test_cli_succeeds_without_subcommand(runner):
    result = runner.invoke(cli)
    assert result.exit_code == 0
import itertools


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
            

@pytest.mark.parametrize("addrport, expected", [
    ("localhost:8000", ("localhost", 8000)),  # Valid hostname.
    ("127.0.0.1:8080", ("127.0.0.1", 8080)),  # Valid IP address.
    ("0.0.0.0:5000", ("0.0.0.0", 5000)),  # Valid 0.0.0.0 binding.
    ("8000", (DEFAULT_HOST, 8000)),  # Default host.
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