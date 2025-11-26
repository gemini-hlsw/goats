from unittest.mock import MagicMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory

from goats_tom.api_views.status.status import StatusViewSet


@pytest.fixture
def api_rf():
    return APIRequestFactory()

@pytest.fixture
def status_viewset():
    return StatusViewSet()

@pytest.fixture
def mock_status_mixins(monkeypatch):
    mock_mixins = {
        "service1": {
            "display_name": "Service 1",
            "endpoint": "/status/service1",
            "instance": MagicMock(spec=["get"]),
        },
        "service2": {
            "display_name": "Service 2",
            "endpoint": "/status/service2",
            "instance": MagicMock(spec=["get"]),
        },
    }
    monkeypatch.setattr("goats_tom.api_views.status.status.status_mixins", mock_mixins)
    return mock_mixins

def test_list_status(api_rf, status_viewset, mock_status_mixins):
    request = api_rf.get("/status/")
    response = status_viewset.list(request)

    assert response.status_code == status.HTTP_200_OK
    assert "services" in response.data
    assert "status_codes" in response.data
    assert response.data["message"] == "Available services and details"
    assert len(response.data["services"]) == len(mock_status_mixins)

    for service in response.data["services"]:
        assert set(service) == {"name", "display_name", "endpoint"}

def test_status_router_valid_service(api_rf, status_viewset, mock_status_mixins):
    service_name = "service1"
    request = api_rf.get(f"/status/{service_name}/")

    mock_instance = mock_status_mixins[service_name]["instance"]
    mock_response = MagicMock(status_code=status.HTTP_200_OK, data={"status": "ok"})
    mock_instance.get.return_value = mock_response

    response = status_viewset.status_router(request, service=service_name)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "ok"}
    mock_instance.get.assert_called_once_with(request)

def test_status_router_invalid_service(api_rf, status_viewset):
    request = api_rf.get("/status/unknown/")
    response = status_viewset.status_router(request, service="unknown")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data == {"detail": "Unknown status service: unknown"}
