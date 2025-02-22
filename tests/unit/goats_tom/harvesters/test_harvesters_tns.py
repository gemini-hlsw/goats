import pytest
from unittest.mock import MagicMock, patch
from astropy.coordinates import SkyCoord
from tom_targets.models import BaseTarget
from goats_tom.harvesters import TNSHarvester

import requests

@pytest.fixture
def mock_tns_client():
    """Fixture to mock the TNSClient and its methods."""
    client = MagicMock()
    client.get_object.return_value = {
        "name": "TestObject",
        "right_ascension": "12:34:56.78",
        "declination": "-12:34:56.7",
    }
    return client


@pytest.fixture
def harvester(mock_tns_client):
    """Fixture to create a TNSHarvester instance with a mocked TNSClient."""
    with patch("goats_tom.harvesters.tns.TNSClient", return_value=mock_tns_client):
        harvester = TNSHarvester()
    return harvester


def test_tns_harvester_query(harvester: TNSHarvester, mock_tns_client: MagicMock):
    """Test the query method of TNSHarvester."""
    term = "TestObject"
    harvester.query(term)

    # Ensure the client was called with the correct term.
    mock_tns_client.get_object.assert_called_once_with(term)

    # Verify catalog_data is set correctly.
    assert harvester.catalog_data["name"] == "TestObject"
    assert harvester.catalog_data["right_ascension"] == "12:34:56.78"
    assert harvester.catalog_data["declination"] == "-12:34:56.7"


def test_tns_harvester_to_target(harvester: TNSHarvester):
    """Test the to_target method of TNSHarvester."""
    harvester.catalog_data = {
        "name": "TestObject",
        "right_ascension": "12:34:56.78",
        "declination": "-12:34:56.7",
    }

    target = harvester.to_target()

    # Validate target properties.
    assert isinstance(target, BaseTarget)
    assert target.name == "TestObject"
    assert target.type == "SIDEREAL"

    # Validate RA and Dec conversion.
    c = SkyCoord("12:34:56.78 -12:34:56.7", unit=("hourangle", "deg"))
    assert target.ra == pytest.approx(c.ra.deg)
    assert target.dec == pytest.approx(c.dec.deg)


def test_tns_harvester_query_with_http_error(harvester: TNSHarvester, mock_tns_client: MagicMock):
    """Test the query method when an HTTP error occurs."""
    mock_tns_client.get_object.side_effect = requests.HTTPError

    term = "TestObject"
    harvester.query(term)

    # Ensure catalog_data is empty after the error.
    assert harvester.catalog_data == {}