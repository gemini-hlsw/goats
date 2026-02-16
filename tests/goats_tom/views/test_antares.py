from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from django.urls import reverse
from tom_targets.models import Target

pytestmark = pytest.mark.django_db


def _make_target(name: str = "ANT2025pgw4bzzmbm67") -> Target:
    # Los campos mínimos dependen de tu modelo, pero normalmente estos bastan.
    return Target.objects.create(
        name=name,
        type="SIDEREAL",
        ra=10.0,
        dec=-10.0,
    )


@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_requires_post(mock_get_service_class, client):
    """
    El view está decorado con require_POST, así que GET debe responder 405.
    """
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    resp = client.get(url)
    assert resp.status_code == 405

    mock_get_service_class.assert_not_called()


@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_no_alerts_redirects_to_referer(mock_get_service_class, client):
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([])

    mock_get_service_class.return_value = lambda: broker

    resp = client.post(url, HTTP_REFERER="/targets/999/")
    assert resp.status_code == 302
    assert resp["Location"] == "/targets/999/"

    broker.fetch_alerts.assert_called_once_with({"locusid": target.name})
    broker.process_lightcurve_data.assert_not_called()
    broker.create_lightcurve_dp.assert_not_called()
    broker.create_reduced_datums.assert_not_called()


@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_lightcurve_none_redirects(mock_get_service_class, client):
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([{"locus_id": target.name}])
    broker.process_lightcurve_data.return_value = None

    mock_get_service_class.return_value = lambda: broker

    resp = client.post(url, HTTP_REFERER="/targets/179/")
    assert resp.status_code == 302
    assert resp["Location"] == "/targets/179/"

    broker.process_lightcurve_data.assert_called_once()
    broker.create_lightcurve_dp.assert_not_called()
    broker.create_reduced_datums.assert_not_called()


@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_lightcurve_empty_df_redirects(mock_get_service_class, client):
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([{"locus_id": target.name}])
    broker.process_lightcurve_data.return_value = pd.DataFrame()  # empty

    mock_get_service_class.return_value = lambda: broker

    resp = client.post(url, HTTP_REFERER="/targets/179/")
    assert resp.status_code == 302
    assert resp["Location"] == "/targets/179/"

    broker.create_lightcurve_dp.assert_not_called()
    broker.create_reduced_datums.assert_not_called()


@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_success_calls_broker_and_redirects(
    mock_get_service_class, client
):
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    df = pd.DataFrame(
        {
            "time": [60000.0, 60001.0],
            "magnitude": [19.0, 19.1],
            "error": [0.1, 0.1],
            "filter": ["r", "r"],
        }
    )

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([{"locus_id": target.name}])
    broker.process_lightcurve_data.return_value = df

    dp = MagicMock()
    dp.id = 123
    broker.create_lightcurve_dp.return_value = dp

    mock_get_service_class.return_value = lambda: broker

    resp = client.post(url, HTTP_REFERER="/targets/179/")
    assert resp.status_code == 302
    assert resp["Location"] == "/targets/179/"

    broker.fetch_alerts.assert_called_once_with({"locusid": target.name})
    broker.process_lightcurve_data.assert_called_once()
    broker.create_lightcurve_dp.assert_called_once_with(target, df)
    broker.create_reduced_datums.assert_called_once_with(dp)


@patch("goats_tom.views.antares.logger")
@patch("goats_tom.views.antares.tom_alerts_get_service_class")
def test_refresh_antares_broker_exception_is_caught_and_redirects(
    mock_get_service_class, mock_logger, client
):
    target = _make_target()
    url = reverse("refresh_antares_photometry", kwargs={"target_id": target.id})

    df = pd.DataFrame({"time": [60000.0], "magnitude": [19.0]})

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([{"locus_id": target.name}])
    broker.process_lightcurve_data.return_value = df
    broker.create_lightcurve_dp.side_effect = RuntimeError("boom")

    mock_get_service_class.return_value = lambda: broker

    resp = client.post(url, HTTP_REFERER="/targets/179/")
    assert resp.status_code == 302
    assert resp["Location"] == "/targets/179/"

    # Se espera que lo capture y loguee (según tu código)
    assert mock_logger.exception.call_count >= 1
