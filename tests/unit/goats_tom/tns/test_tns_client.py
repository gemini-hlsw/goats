import pytest
import requests
from unittest.mock import MagicMock
from pathlib import Path

from bs4 import BeautifulSoup
from goats_tom.tns import TNSClient


@pytest.fixture
def tns_html() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "tns-20250123.html"


@pytest.fixture
def client() -> TNSClient:
    """Returns a TNSClient instance for tests."""
    return TNSClient(timeout=10)


def test_parse_object_name_from_title(client: TNSClient, tns_html: Path) -> None:
    html = tns_html.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    name = client._parse_object_name_from_title(soup)
    assert name == "AT 2025zt"


def test_parse_value_from_div_container(client: TNSClient, tns_html: Path) -> None:
    html = tns_html.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    val = client._parse_value_from_div_container(soup, "field-type")
    assert val == "---"

    val_none = client._parse_value_from_div_container(soup, "field-missing")
    assert val_none is None


def test_parse_radec_from_value(client: TNSClient) -> None:
    # Good input.
    ra, dec = client._parse_radec_from_value("12:34:56.78 +12:34:56.7")
    assert ra == "12:34:56.78"
    assert dec == "+12:34:56.7"

    # Missing or partial input.
    ra_none, dec_none = client._parse_radec_from_value(None)
    assert ra_none is None and dec_none is None

    ra_only, dec_only = client._parse_radec_from_value("12:34:56.78")
    assert ra_only is None
    assert dec_only is None


def test_parse_object_html(client: TNSClient, tns_html: Path) -> None:
    html = tns_html.read_text(encoding="utf-8")
    result = client._parse_object_html(html)

    assert result["name"] == "AT 2025zt"
    assert result["type"] == "---"
    assert result["right_ascension"] == "00:59:42.324"
    assert result["declination"] == "+26:39:05.16"
    assert result["redshift"] == ""
    assert result["reporting_group"] == "ATLAS"
    assert result["discovering_data_source"] == "ATLAS"
    assert result["discovery_date"] == "2025-01-22 06:12:23.040"
    assert result["tns_at"] == "Y"
    assert result["public"] == "Y"
    assert result["discovery_magnitude"] == "19.18"
    assert result["filter"] == "cyan-ATLAS"


def test_get_object_success(monkeypatch, client: TNSClient, tns_html: Path) -> None:
    """Test that get_object successfully returns parsed data when the request
    returns a 200 status code.
    """
    # Mock the Response object
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = tns_html.read_text(encoding="utf-8")

    # Mock Session.get to return our mock_response
    def mock_get(url, timeout=5):
        return mock_response

    monkeypatch.setattr(client._session, "get", mock_get)

    data = client.get_object("AT_2025zt")
    assert data["name"] == "AT 2025zt"
    assert data["type"] == "---"


def test_get_object_http_error(monkeypatch, client: TNSClient) -> None:
    """Test that get_object raises an HTTPError when the response is non-2xx."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("Not Found")
    mock_response.status_code = 404
    mock_response.text = "Error"

    def mock_get(url, timeout=5):
        return mock_response

    monkeypatch.setattr(client._session, "get", mock_get)

    with pytest.raises(requests.HTTPError):
        client.get_object("non_existent_object")

@pytest.mark.remote_data()
def test_remote_get_object_success(client: TNSClient) -> None:
    result = client.get_object("2025zt")
    assert result["name"] == "AT 2025zt"
    assert result["type"] == "---"
    assert result["right_ascension"] == "00:59:42.324"
    assert result["declination"] == "+26:39:05.16"
    assert result["redshift"] == ""
    assert result["reporting_group"] == "ATLAS"
    assert result["discovering_data_source"] == "ATLAS"
    assert result["discovery_date"] == "2025-01-22 06:12:23.040"
    assert result["tns_at"] == "Y"
    assert result["public"] == "Y"
    assert result["discovery_magnitude"] == "19.18"
    assert result["filter"] == "cyan-ATLAS"

@pytest.mark.remote_data()
def test_remote_get_object_failure(client: TNSClient):
    with pytest.raises(requests.HTTPError):
        client.get_object("non_existent_object")