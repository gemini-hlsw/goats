from json import JSONDecodeError
from unittest.mock import Mock

import requests
from requests import HTTPError, RequestException, Timeout

from goats_common.version_checker import PACKAGE_NAME, VersionChecker


def _fake_response(json_payload=None, status_code=200, json_raises=None) -> requests.Response:
    """Build a Response-like mock with controllable .json() and status."""
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    if json_raises is not None:
        resp.json.side_effect = json_raises
    else:
        resp.json.return_value = json_payload
    return resp


def test_outdated_true(monkeypatch):
    """current < latest → is_outdated == True and status=success."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    payload = {"packages": {PACKAGE_NAME: {"version": "1.2.0"}}}
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload))

    vc = VersionChecker()
    assert vc.current_version == "1.0.0"
    assert vc.latest_version == "1.2.0"
    assert vc.is_outdated is True

    snap = vc.as_dict()
    assert snap["status"] == "success"
    assert snap["current"] == "1.0.0"
    assert snap["latest"] == "1.2.0"
    assert snap["is_outdated"] is True


def test_uptodate_false(monkeypatch):
    """current == latest → is_outdated == False and status=success."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.2.0")
    payload = {"packages": {PACKAGE_NAME: {"version": "1.2.0"}}}
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload))

    vc = VersionChecker()
    assert vc.is_outdated is False
    assert vc.as_dict()["status"] == "success"


def test_timeout_sets_error_and_none(monkeypatch, caplog):
    """Timeout → latest=None, is_outdated=None, status=error and WARNING log."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: (_ for _ in ()).throw(Timeout("slow")))

    with caplog.at_level("WARNING"):
        vc = VersionChecker()
        _ = vc.latest_version  # force evaluation
        snap = vc.as_dict()

    assert vc.latest_version is None
    assert vc.is_outdated is None
    assert snap["status"] == "error"
    assert "errors" in snap and any("Timed out" in e for e in snap["errors"])
    assert any("Timed out fetching channel metadata" in r.message for r in caplog.records)


def test_request_exception_sets_error(monkeypatch, caplog):
    """RequestException → status=error."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: (_ for _ in ()).throw(RequestException("net")))

    with caplog.at_level("WARNING"):
        vc = VersionChecker()
        snap = vc.as_dict()

    assert snap["status"] == "error"
    assert any("Failed to fetch latest version" in e for e in snap.get("errors", []))


def test_invalid_json_sets_error(monkeypatch, caplog):
    """JSONDecodeError → status=error."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    resp = _fake_response(json_raises=JSONDecodeError("bad", "x", 0))
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: resp)

    with caplog.at_level("WARNING"):
        vc = VersionChecker()
        snap = vc.as_dict()

    assert snap["status"] == "error"
    assert any("Invalid JSON" in e for e in snap.get("errors", []))


def test_malformed_metadata_sets_error(monkeypatch, caplog):
    """KeyError/TypeError → status=error."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    payload = {"packages": {"other": {"version": "9.9.9"}}}  # missing expected package
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload))

    with caplog.at_level("WARNING"):
        vc = VersionChecker()
        snap = vc.as_dict()

    assert snap["status"] == "error"
    assert any("Malformed channeldata.json" in e for e in snap.get("errors", []))


def test_invalid_version_format_sets_error(monkeypatch, caplog):
    """Unparseable current version → is_outdated=None and error tracked."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "not-a-version")
    payload = {"packages": {PACKAGE_NAME: {"version": "1.2.3"}}}
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload))

    with caplog.at_level("WARNING"):
        vc = VersionChecker()
        _ = vc.is_outdated  # force comparison
        snap = vc.as_dict()

    assert vc.is_outdated is None
    assert snap["status"] == "error"
    assert any("Invalid version format" in e for e in snap.get("errors", []))


def test_custom_url_timeout_and_package(monkeypatch):
    """Respects channeldata_url, package_name and timeout_sec."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "0.9.0")
    payload = {"packages": {"goats-cli": {"version": "1.0.0"}, PACKAGE_NAME: {"version": "0.1.0"}}}

    seen = {}
    def fake_get(url, timeout):
        seen["url"] = url
        seen["timeout"] = timeout
        return _fake_response(payload)

    monkeypatch.setattr("goats_common.version_checker.requests.get", fake_get)

    url = "https://example.invalid/channel.json"
    vc = VersionChecker(channeldata_url=url, package_name="goats-cli", timeout_sec=5.0)

    assert vc.current_version == "0.9.0"
    assert vc.latest_version == "1.0.0"
    assert vc.is_outdated is True
    assert seen["url"] == url and seen["timeout"] == 5.0


def test_refresh_recomputes(monkeypatch):
    """refresh() invalidates cached_properties and forces recomputation."""
    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.0.0")
    payload1 = {"packages": {PACKAGE_NAME: {"version": "1.1.0"}}}
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload1))

    vc = VersionChecker()
    assert vc.current_version == "1.0.0"
    assert vc.latest_version == "1.1.0"
    assert vc.is_outdated is True

    monkeypatch.setattr("goats_common.version_checker.get_version", lambda _: "1.2.0")
    payload2 = {"packages": {PACKAGE_NAME: {"version": "1.2.0"}}}
    monkeypatch.setattr("goats_common.version_checker.requests.get", lambda *a, **k: _fake_response(payload2))

    vc.refresh()
    assert vc.current_version == "1.2.0"
    assert vc.latest_version == "1.2.0"
    assert vc.is_outdated is False
