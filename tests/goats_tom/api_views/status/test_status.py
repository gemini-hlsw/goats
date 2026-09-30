import pytest
from unittest.mock import MagicMock
from rest_framework.test import APIRequestFactory
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
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
            "group": "account",
            "url": None,
            "url_label": "Explore",
            "manage_url_name": "user-gpp-login",
            "instance": MagicMock(spec=["get", "get_public_url"]),
        },
        "service2": {
            "display_name": "Service 2",
            "endpoint": "/status/service2",
            "group": "account",
            "url": None,
            "url_label": None,
            "manage_url_name": None,
            "instance": MagicMock(
                spec=["get", "get_public_url"],
                **{"get_public_url.return_value": "https://service2.example"},
            ),
        },
    }
    monkeypatch.setattr("goats_tom.api_views.status.status.status_mixins", mock_mixins)
    return mock_mixins

def test_list_status(api_rf, status_viewset, mock_status_mixins):
    request = api_rf.get("/status/")
    request.user = MagicMock(is_authenticated=True, pk=7)
    response = status_viewset.list(request)

    assert response.status_code == status.HTTP_200_OK
    assert "services" in response.data
    assert "status_codes" in response.data
    assert response.data["message"] == "Available services and details"
    assert len(response.data["services"]) == len(mock_status_mixins)

    for service in response.data["services"]:
        assert set(service) == {
            "name",
            "display_name",
            "endpoint",
            "group",
            "url",
            "url_label",
            "manage_url",
        }

    # The link says where it goes, which may not be the service itself.
    assert [s["url_label"] for s in response.data["services"]] == [
        "Explore",
        "Service 2",
    ]
    # Without a website of its own, a service links to the URL it checks.
    assert response.data["services"][1]["url"] == "https://service2.example"

    manage_urls = [s["manage_url"] for s in response.data["services"]]
    assert manage_urls == ["/users/7/gpp/", None]


def test_list_status_anonymous_has_no_manage_url(
    api_rf, status_viewset, mock_status_mixins
):
    request = api_rf.get("/status/")
    request.user = MagicMock(is_authenticated=False)
    response = status_viewset.list(request)

    assert all(s["manage_url"] is None for s in response.data["services"])

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


def test_status_api_requires_login():
    assert [type(p) for p in StatusViewSet().get_permissions()] == [IsAuthenticated]


@pytest.mark.django_db
def test_status_page_requires_login(client):
    response = client.get("/status/")

    assert response.status_code == 302
    assert "login" in response.url
