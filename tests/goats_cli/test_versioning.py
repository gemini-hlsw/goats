import pytest
from json import JSONDecodeError
from unittest.mock import Mock, patch
from requests import RequestException, HTTPError
import requests

from goats_cli.versioning import VersionChecker
from goats_cli.exceptions import GOATSClickException


def _fake_response(json_payload=None, status_code=200, json_raises=None) -> requests.Response:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = HTTPError(f"status={status_code}")
    else:
        resp.raise_for_status.return_value = None
    if json_raises is not None:
        resp.json.side_effect = json_raises
    else:
        resp.json.return_value = json_payload
    return resp


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_is_outdated_true(mock_get, _mock_get_version):
    payload = {"packages": {"goats": {"version": "1.2.0"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    vc = VersionChecker()
    assert vc.check_if_outdated() is True

    assert vc.current_version == "1.0.0"
    assert vc.latest_version == "1.2.0"
    assert vc.is_outdated is True

    mock_get.assert_called_once()
    called_kwargs = mock_get.call_args.kwargs
    assert called_kwargs["timeout"] == 1.0


@patch("goats_cli.versioning.get_version", return_value="1.2.0")
@patch("goats_cli.versioning.requests.get")
def test_is_outdated_false_equal(mock_get, _):
    payload = {"packages": {"goats": {"version": "1.2.0"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    vc = VersionChecker()
    assert vc.check_if_outdated() is False
    assert vc.is_outdated is False


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_request_exception_wraps_in_goatsclick(mock_get, _):
    mock_get.side_effect = RequestException("network down")

    vc = VersionChecker()
    with pytest.raises(GOATSClickException) as exc:
        vc.check_if_outdated()
    assert "Failed to fetch latest version info" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_jsondecodeerror_is_caught(mock_get, _):
    mock_get.return_value = _fake_response(
        json_raises=JSONDecodeError("Invalid JSON", doc="<<<", pos=1)
    )

    vc = VersionChecker()
    with pytest.raises(GOATSClickException) as exc:
        vc.check_if_outdated()
    assert "Invalid JSON" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_malformed_structure_keyerror(mock_get, _):
    payload = {"packages": {"other": {"version": "9.9.9"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    vc = VersionChecker()
    with pytest.raises(GOATSClickException) as exc:
        vc.check_if_outdated()
    assert "Malformed channel metadata" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_malformed_structure_typeerror(mock_get, _):
    mock_get.return_value = _fake_response(json_payload=["not", "a", "dict"])

    vc = VersionChecker()
    with pytest.raises(GOATSClickException) as exc:
        vc.check_if_outdated()
    assert "Malformed channel metadata" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="0.9.0")
@patch("goats_cli.versioning.requests.get")
def test_custom_url_timeout_and_package(mock_get, _):
    payload = {
        "packages": {
            "goats-cli": {"version": "1.0.0"},
            "goats": {"version": "0.1.0"},
        }
    }
    mock_get.return_value = _fake_response(json_payload=payload)

    url = "https://example.invalid/channel.json"
    vc = VersionChecker(channeldata_url=url, package_name="goats-cli", timeout_sec=5.0)

    assert vc.check_if_outdated() is True
    assert vc.current_version == "0.9.0"
    assert vc.latest_version == "1.0.0"
    assert vc.is_outdated is True

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == url
    assert kwargs["timeout"] == 5.0

@pytest.mark.remote_data()
def test_get_latest_version_live():
    checker = VersionChecker()
    assert isinstance(checker.check_if_outdated(), bool)
    assert isinstance(checker.latest_version, str)
