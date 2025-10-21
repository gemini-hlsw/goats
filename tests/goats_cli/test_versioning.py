import pytest
from json import JSONDecodeError
from unittest.mock import Mock, patch
from requests import RequestException, HTTPError
import requests  # used for requests.Response in spec

from goats_cli.versioning import VersionChecker
from goats_cli.exceptions import GOATSClickException


def _fake_response(json_payload=None, status_code=200, json_raises=None) -> requests.Response:
    """
    Build a Mock that simulates requests.Response.
    Uses spec=requests.Response to validate the real interface.
    """
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
def test_is_outdated_true(mock_get, mock_get_version):
    payload = {"packages": {"goats": {"version": "1.2.0"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    vc = VersionChecker()
    assert vc.current_version == "1.0.0"
    assert vc.latest_version == "1.2.0"
    assert vc.is_outdated is True

    mock_get.assert_called_once()
    # Ensure default timeout was passed
    called_kwargs = mock_get.call_args.kwargs
    assert called_kwargs["timeout"] == 10.0


@patch("goats_cli.versioning.get_version", return_value="1.2.0")
@patch("goats_cli.versioning.requests.get")
def test_is_outdated_false_equal(mock_get, _):
    payload = {"packages": {"goats": {"version": "1.2.0"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    vc = VersionChecker()
    assert vc.is_outdated is False


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_request_exception_wraps_in_goatsclick(mock_get, _):
    mock_get.side_effect = RequestException("network down")
    with pytest.raises(GOATSClickException) as exc:
        VersionChecker()
    assert "Failed to fetch latest version info" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_jsondecodeerror_is_caught(mock_get, _):
    mock_get.return_value = _fake_response(
        json_raises=JSONDecodeError("Invalid JSON", doc="<<<", pos=1)
    )
    with pytest.raises(GOATSClickException) as exc:
        VersionChecker()
    assert "Invalid JSON" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_malformed_structure_keyerror(mock_get, _):
    # Missing "goats" or "version" keys
    payload = {"packages": {"other": {"version": "9.9.9"}}}
    mock_get.return_value = _fake_response(json_payload=payload)

    with pytest.raises(GOATSClickException) as exc:
        VersionChecker()
    assert "Malformed channel metadata" in str(exc.value)


@patch("goats_cli.versioning.get_version", return_value="1.0.0")
@patch("goats_cli.versioning.requests.get")
def test_malformed_structure_typeerror(mock_get, _):
    # Valid JSON but unexpected type (list instead of dict)
    mock_get.return_value = _fake_response(json_payload=["not", "a", "dict"])

    with pytest.raises(GOATSClickException) as exc:
        VersionChecker()
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

    assert vc.current_version == "0.9.0"
    assert vc.latest_version == "1.0.0"
    assert vc.is_outdated is True

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == url
    assert kwargs["timeout"] == 5.0

