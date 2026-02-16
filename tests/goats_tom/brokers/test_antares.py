from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from astropy.time import Time, TimezoneInfo
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from goats_tom.brokers import ANTARESBroker, ANTARESBrokerForm
from tom_alerts.alerts import GenericAlert
from tom_targets.models import Target


@pytest.fixture
def broker():
    return ANTARESBroker()


@pytest.fixture
def target_mock():
    t = MagicMock()
    t.name = "ANT123"
    return t


@pytest.mark.django_db()
def test_antaresbroker_form_valid():
    form_data = {
        "query": {"query": "some valid query"},
        "query_name": "test",
        "broker": "ANTARES",
    }
    form = ANTARESBrokerForm(data=form_data)
    assert form.is_valid()


@pytest.mark.django_db()
def test_antaresbroker_form_invalid():
    form = ANTARESBrokerForm(data={})
    assert not form.is_valid()
    with pytest.raises(ValidationError):
        form.clean()


@pytest.mark.django_db()
def test_antaresbroker_form_no_data():
    form = ANTARESBrokerForm()
    assert not form.is_valid()


@pytest.mark.django_db()
@patch("goats_tom.brokers.antares.get_by_id")
@patch("goats_tom.brokers.antares.search")
def test_fetch_alerts_locusid(mock_search, mock_get_by_id, broker):
    mock_locus = MagicMock()
    mock_locus.locus_id = "test_locus"
    mock_get_by_id.return_value = mock_locus

    alerts = list(broker.fetch_alerts({"locusid": "test_locus"}))

    assert len(alerts) == 1
    assert alerts[0]["locus_id"] == "test_locus"
    mock_get_by_id.assert_called_once_with("test_locus")
    mock_search.assert_not_called()


@pytest.mark.django_db()
@patch("goats_tom.brokers.antares.get_by_id")
@patch("goats_tom.brokers.antares.search")
def test_fetch_alerts_query(mock_search, mock_get_by_id, broker):
    mock_locus = MagicMock()
    mock_locus.locus_id = "test_locus"
    mock_search.return_value = iter([mock_locus])

    alerts = list(broker.fetch_alerts({"query": {"query": "test"}}))

    assert len(alerts) == 1
    assert alerts[0]["locus_id"] == "test_locus"
    mock_search.assert_called_once()
    mock_get_by_id.assert_not_called()


def test_alert_to_dict():
    locus_mock = MagicMock()
    locus_mock.locus_id = "test_locus"
    locus_mock.ra = 123.45
    locus_mock.dec = -54.32
    locus_mock.properties = {"key": "value"}
    locus_mock.tags = ["tag1"]
    locus_mock.catalogs = {"catalog1": "data"}
    locus_mock.alerts = [
        MagicMock(alert_id="alert1", mjd=59000.5, properties={"prop": "v"})
    ]

    result = ANTARESBroker.alert_to_dict(locus_mock)

    assert result["locus_id"] == "test_locus"
    assert result["ra"] == 123.45
    assert result["dec"] == -54.32
    assert result["alerts"][0]["alert_id"] == "alert1"


@pytest.mark.django_db()
def test_to_target(broker):
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
def test_to_generic_alert(broker):
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
    assert generic_alert.mag == 20.5
    assert generic_alert.score == 0.9
    assert generic_alert.timestamp == Time(
        59000.5, format="mjd", scale="utc"
    ).to_datetime(timezone=TimezoneInfo())


@pytest.mark.django_db()
def test_extract_survey_aliases(broker):
    target = Target.objects.create(
        name="test_target",
        type="SIDEREAL",
        ra=123.45,
        dec=-54.32,
    )

    alert = {
        "properties": {
            "horizons_targetname": "HorizonsName",
            "survey": {
                "ztf": {"id": ["ZTF1"]},
                "lsst": {"dia_object_id": ["LSST1"]},
            },
        },
    }

    aliases = broker.extract_survey_aliases(target, alert)

    alias_names = [alias.name for alias in aliases]
    assert "HorizonsName" in alias_names
    assert "ZTF1" in alias_names
    assert "LSST1" in alias_names


def test_process_lightcurve_data_none_returns_none(broker):
    assert broker.process_lightcurve_data(alert={}) is None


def test_process_lightcurve_data_success(broker):
    alert = {
        "lightcurve": [
            {
                "ant_mjd": 60000.0,
                "ant_mag": 18.2,
                "ant_magerr": 0.1,
                "ant_maglim": None,
                "ant_passband": "r",
            }
        ],
        "properties": {"survey": {"ztf": {}}},
    }

    df = broker.process_lightcurve_data(alert=alert)

    assert df is not None
    assert "magnitude" in df.columns
    assert (df["source"] == "ANTARES").all()
    assert (df["telescope"] == "ZTF").all()


def test_process_lightcurve_data_telescope_unknown(broker):
    alert = {
        "lightcurve": [{"ant_mjd": 1.0, "ant_mag": 18.0}],
        "properties": {},
    }

    df = broker.process_lightcurve_data(alert=alert)

    assert (df["telescope"] == "UNKNOWN").all()


@pytest.mark.django_db(transaction=True)
@patch("goats_tom.brokers.antares.ContentFile")
@patch("goats_tom.brokers.antares.DataProduct")
def test_create_lightcurve_dp_created(
    mock_dataproduct, mock_contentfile, broker, target_mock
):
    lightcurve = pd.DataFrame([{"time": 1.0, "magnitude": 18.0}])

    dp = MagicMock()
    dp.id = 10
    dp.data = MagicMock()

    mock_dataproduct.objects.get_or_create.return_value = (dp, True)

    result = broker.create_lightcurve_dp(target_mock, lightcurve)

    assert result is dp
    dp.data.save.assert_called_once()


@pytest.mark.django_db(transaction=True)
@patch("goats_tom.brokers.antares.ContentFile")
@patch("goats_tom.brokers.antares.DataProduct")
def test_create_lightcurve_dp_integrityerror(
    mock_dataproduct, mock_contentfile, broker, target_mock
):
    lightcurve = pd.DataFrame([{"time": 1.0}])

    dp = MagicMock()
    dp.id = 11
    dp.data = MagicMock()

    mock_dataproduct.objects.get_or_create.side_effect = IntegrityError()
    mock_dataproduct.objects.get.return_value = dp

    result = broker.create_lightcurve_dp(target_mock, lightcurve)

    assert result is dp
    dp.data.save.assert_called_once()


@patch("goats_tom.brokers.antares.ReducedDatum")
@patch("goats_tom.brokers.antares.run_data_processor")
def test_create_reduced_datums_success(mock_run, mock_reduceddatum, broker):
    dp = MagicMock()
    dp.id = 123

    broker.create_reduced_datums(dp)

    mock_run.assert_called_once_with(dp)
    dp.delete.assert_not_called()


@patch("goats_tom.brokers.antares.ReducedDatum")
@patch("goats_tom.brokers.antares.run_data_processor")
def test_create_reduced_datums_failure(mock_run, mock_reduceddatum, broker):
    dp = MagicMock()
    dp.id = 123

    mock_run.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        broker.create_reduced_datums(dp)

    mock_reduceddatum.objects.filter.assert_called_once_with(data_product=dp)
    dp.delete.assert_called_once()
