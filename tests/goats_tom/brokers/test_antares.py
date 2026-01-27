from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError

from goats_tom.brokers import ANTARESBroker, ANTARESBrokerForm
from unittest.mock import MagicMock, patch
from astropy.time import Time, TimezoneInfo
from tom_alerts.alerts import GenericAlert
from tom_targets.models import Target


@pytest.mark.django_db()
def test_antaresbroker_form_valid():
    """Test the form with valid data.
    """
    form_data = {
        "query": {"query": "some valid query"},
        "query_name": "test",
        "broker": "ANTARES",
    }
    form = ANTARESBrokerForm(data=form_data)
    assert form.is_valid(), "Form should be valid with correct query data."


@pytest.mark.django_db()
def test_antaresbroker_form_invalid():
    """Test the form with invalid data.
    """
    form_data = {}
    form = ANTARESBrokerForm(data=form_data)
    assert not form.is_valid(), "Form should not be valid with empty query."

    with pytest.raises(ValidationError):
        form.clean()


@pytest.mark.django_db()
def test_antaresbroker_form_no_data():
    """Test the form with no data.
    """
    form = ANTARESBrokerForm()
    assert not form.is_valid(), "Form should not be valid without data."


@pytest.mark.remote_data()
def test_fetch_alerts_locusid_remote():
    broker = ANTARESBroker()
    parameters = {"locusid": "ANT2020j7wo4"}  # Example parameter
    alerts = broker.fetch_alerts(parameters)
    assert isinstance(alerts, Iterator)


@pytest.mark.remote_data()
def test_fetch_alerts_query_remote():
    broker = ANTARESBroker()
    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "properties.num_mag_values": {
                                "gte": 50,
                                "lte": 100,
                            },
                        },
                    },
                    {"term": {"tags": "nuclear_transient"}},
                ],
            },
        },
    }
    parameters = {"query": query}  # Example parameter
    alerts = broker.fetch_alerts(parameters)
    assert isinstance(alerts, Iterator)

@pytest.mark.django_db()
def test_alert_to_dict():
    """Test the alert_to_dict method."""
    locus_mock = MagicMock()
    locus_mock.locus_id = "test_locus"
    locus_mock.ra = 123.45
    locus_mock.dec = -54.32
    locus_mock.properties = {"key": "value"}
    locus_mock.tags = ["tag1", "tag2"]
    locus_mock.catalogs = {"catalog1": "data"}
    locus_mock.alerts = [
        MagicMock(alert_id="alert1", mjd=59000.5, properties={"prop1": "value1"}),
        MagicMock(alert_id="alert2", mjd=59001.5, properties={"prop2": "value2"}),
    ]

    result = ANTARESBroker.alert_to_dict(locus_mock)

    assert result["locus_id"] == "test_locus"
    assert result["ra"] == 123.45
    assert result["dec"] == -54.32
    assert result["properties"] == {"key": "value"}
    assert result["tags"] == ["tag1", "tag2"]
    assert result["catalogs"] == {"catalog1": "data"}
    assert len(result["alerts"]) == 2
    assert result["alerts"][0]["alert_id"] == "alert1"
    assert result["alerts"][1]["alert_id"] == "alert2"


@pytest.mark.django_db()
@patch("goats_tom.brokers.antares.get_by_id")
@patch("goats_tom.brokers.antares.search")
def test_fetch_alerts_locusid(mock_search, mock_get_by_id):
    """Test fetch_alerts with a locus ID."""
    broker = ANTARESBroker()
    mock_locus = MagicMock()
    mock_locus.locus_id = "test_locus"
    mock_get_by_id.return_value = mock_locus

    parameters = {"locusid": "test_locus"}
    alerts = list(broker.fetch_alerts(parameters))

    assert len(alerts) == 1
    assert alerts[0]["locus_id"] == "test_locus"
    mock_get_by_id.assert_called_once_with("test_locus")
    mock_search.assert_not_called()


@pytest.mark.django_db()
@patch("goats_tom.brokers.antares.get_by_id")
@patch("goats_tom.brokers.antares.search")
def test_fetch_alerts_query(mock_search, mock_get_by_id):
    """Test fetch_alerts with a query."""
    broker = ANTARESBroker()
    mock_locus = MagicMock()
    mock_locus.locus_id = "test_locus"
    mock_search.return_value = iter([mock_locus])

    parameters = {"query": {"query": "test_query"}}
    alerts = list(broker.fetch_alerts(parameters))

    assert len(alerts) == 1
    assert alerts[0]["locus_id"] == "test_locus"
    mock_search.assert_called_once_with({"query": "test_query"})
    mock_get_by_id.assert_not_called()


@pytest.mark.django_db()
def test_to_target():
    """Test the to_target method."""
    broker = ANTARESBroker()
    alert = {
        "locus_id": "test_locus",
        "ra": 123.45,
        "dec": -54.32,
        "properties": {},
    }

    target, extra_data, aliases = broker.to_target(alert)

    assert target.name == "test_locus"
    assert target.ra == 123.45
    assert target.dec == -54.32
    assert target.type == "SIDEREAL"
    assert extra_data == {}
    assert isinstance(aliases, list)


@pytest.mark.django_db()
def test_to_generic_alert():
    """Test the to_generic_alert method."""
    broker = ANTARESBroker()
    alert = {
        "locus_id": "test_locus",
        "ra": 123.45,
        "dec": -54.32,
        "properties": {
            "newest_alert_observation_time": 59000.5,
            "newest_alert_magnitude": 20.5,
        },
        "alerts": [{"properties": {"ztf_rb": 0.9}}],
    }

    generic_alert = broker.to_generic_alert(alert)

    assert isinstance(generic_alert, GenericAlert)
    assert generic_alert.id == "test_locus"
    assert generic_alert.ra == 123.45
    assert generic_alert.dec == -54.32
    assert generic_alert.mag == 20.5
    assert generic_alert.score == 0.9
    assert generic_alert.url == "https://antares.noirlab.edu/loci/test_locus"
    assert generic_alert.timestamp == Time(
        59000.5, format="mjd", scale="utc"
    ).to_datetime(timezone=TimezoneInfo())


@pytest.mark.django_db()
def test_extract_survey_aliases():
    """Test the extract_survey_aliases method."""
    broker = ANTARESBroker()
    target = Target.objects.create(name="test_target", type="SIDEREAL", ra=123.45, dec=-54.32)
    alert = {
        "properties": {
            "horizons_targetname": "HorizonsName",
            "survey": {
                "ztf": {"id": ["ZTF1", "ZTF2"]},
                "lsst": {"dia_object_id": ["LSST1"], "ss_object_id": ["LSST2"]},
            },
        },
    }

    aliases = broker.extract_survey_aliases(target, alert)

    assert len(aliases) == 5
    alias_names = [alias.name for alias in aliases]
    assert "HorizonsName" in alias_names
    assert "ZTF1" in alias_names
    assert "ZTF2" in alias_names
    assert "LSST1" in alias_names
    assert "LSST2" in alias_names
