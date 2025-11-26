import webbrowser

import pytest
import typer

from goats_cli import utils
from goats_cli.config import config


@pytest.mark.parametrize("connect_ex_return, expected", [(0, True), (1, False)])
def test_port_in_use(mocker, connect_ex_return, expected):
    """port_in_use returns True when socket.connect_ex == 0."""
    mock_sock = mocker.MagicMock()
    mock_sock.__enter__.return_value = mock_sock
    mock_sock.__exit__.return_value = False
    mocker.patch("socket.socket", return_value=mock_sock)
    mock_sock.connect_ex.return_value = connect_ex_return

    assert utils.port_in_use("localhost", 1234) is expected
    mock_sock.connect_ex.assert_called_once_with(("localhost", 1234))


def test_check_port_not_in_use_available(mocker):
    """check_port_not_in_use prints success when free."""
    mocker.patch("goats_cli.utils.port_in_use", return_value=False)
    mock_success = mocker.patch("goats_cli.output.success")

    utils.check_port_not_in_use("Redis", "localhost", 6379)

    mock_success.assert_called_once()


def test_check_port_not_in_use_in_use(mocker):
    """check_port_not_in_use raises typer.Exit when used."""
    mocker.patch("goats_cli.utils.port_in_use", return_value=True)
    mock_fail = mocker.patch("goats_cli.output.fail")

    with pytest.raises(typer.Exit):
        utils.check_port_not_in_use("Redis", "localhost", 6379)

    mock_fail.assert_called_once()


def test_wait_until_responsive_success_first_try(mocker):
    """wait_until_responsive returns True when first request returns 200."""
    mocker.patch("time.time", side_effect=[0, 1])  # within timeout
    mocker.patch("requests.get", return_value=mocker.Mock(status_code=200))

    assert utils.wait_until_responsive("http://x", timeout=10) is True


def test_wait_until_responsive_timeout(mocker):
    """wait_until_responsive returns False after repeated exceptions."""
    mock_time = mocker.patch(
        "time.time",
        side_effect=[0, 1, 2, 3, 20],  # simulate time passing beyond timeout
    )
    mocker.patch("requests.get", side_effect=Exception("boom"))
    mock_sleep = mocker.patch("time.sleep")
    mock_warn = mocker.patch("goats_cli.output.warning")

    result = utils.wait_until_responsive("http://x", timeout=5, retry_interval=1)

    assert result is False
    assert mock_sleep.call_count >= 1
    mock_warn.assert_called_once()


@pytest.mark.parametrize(
    "choice, expected_method",
    [
        ("default", "webbrowser.open_new"),
        ("firefox", "webbrowser.get"),
    ],
)
def test_open_browser_success(mocker, choice, expected_method):
    """open_browser opens default or named browser."""
    mock_info = mocker.patch("goats_cli.output.info")

    if choice == "default":
        mock_open = mocker.patch("webbrowser.open_new")
        utils.open_browser("http://x", choice)
        mock_open.assert_called_once_with("http://x")
    else:
        mock_browser = mocker.MagicMock()
        mocker.patch("webbrowser.get", return_value=mock_browser)
        utils.open_browser("http://x", choice)
        mock_browser.open_new.assert_called_once_with("http://x")

    mock_info.assert_called_once()


def test_open_browser_failure(mocker):
    """open_browser prints warning on browser error."""
    mocker.patch("goats_cli.output.info")
    mock_warn = mocker.patch("goats_cli.output.warning")

    # Code catches webbrowser.Error only
    mocker.patch("webbrowser.get", side_effect=webbrowser.Error("bad browser"))

    utils.open_browser("http://x", "opera")

    mock_warn.assert_called_once()


@pytest.mark.parametrize(
    "value, expected",
    [
        ("8000", (config.host, 8000)),
        ("localhost:8000", ("localhost", 8000)),
        ("0.0.0.0:9000", ("0.0.0.0", 9000)),
    ],
)
def test_parse_addrport_valid(value, expected):
    """parse_addrport returns correct (host, port)."""
    assert utils.parse_addrport(value) == expected


@pytest.mark.parametrize("value", ["notaport", "localhost:abc", "bad:123:444"])
def test_parse_addrport_invalid(value):
    """parse_addrport raises ValueError on invalid input."""
    with pytest.raises(ValueError):
        utils.parse_addrport(value)


def test_get_version(mocker):
    """get_version delegates to VersionChecker.current_version."""
    mock_checker = mocker.patch("goats_cli.utils.VersionChecker")
    mock_checker.return_value.current_version = "1.2.3"

    assert utils.get_version() == "1.2.3"
    mock_checker.assert_called_once()


def test_wait(mocker):
    """wait calls time.sleep with given seconds."""
    mock_sleep = mocker.patch("time.sleep")
    utils.wait(2.5)
    mock_sleep.assert_called_once_with(2.5)


@pytest.mark.parametrize("value", ["8000", "0.0.0.0:8000", "localhost:9000"])
def test_validate_addrport_valid(value):
    """validate_addrport returns input if valid."""
    assert utils.validate_addrport(value) == value


@pytest.mark.parametrize("value", ["bad", "123:xyz", "abc:def"])
def test_validate_addrport_invalid(value):
    """validate_addrport raises BadParameter if invalid."""
    with pytest.raises(typer.BadParameter):
        utils.validate_addrport(value)
