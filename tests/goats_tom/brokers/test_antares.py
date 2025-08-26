from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError

from goats_tom.brokers import ANTARESBroker, ANTARESBrokerForm


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
