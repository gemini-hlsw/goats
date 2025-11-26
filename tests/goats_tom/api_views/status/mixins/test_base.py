from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.request import Request

from goats_tom.api_views.status.mixins.base import (
    BaseStatusMixin,
    MissingCredentialsError,
    Status,
    register_status,
    status_mixins,
)


class TestBaseStatusMixin:
    @pytest.fixture
    def mixin(self):
        class TestMixin(BaseStatusMixin):
            service_name = "Test Service"

            def get_credentials(self, request: Request) -> dict:
                return {"api_key": "test_key"}

            def check_service(self, credentials: dict, *args, **kwargs):
                if credentials.get("api_key") == "test_key":
                    return Status.OK, "Service is operational"
                return Status.DOWN, "Invalid credentials"

        return TestMixin()

    @pytest.fixture
    def mock_request(self):
        return MagicMock(spec=Request)

    @patch("goats_tom.api_views.status.mixins.base.datetime")
    def test_get_successful_status(self, mock_datetime, mixin, mock_request):
        # Mock datetime to ensure consistent timestamps
        mock_datetime.now.return_value = datetime(2023, 1, 1, tzinfo=timezone.utc)

        response = mixin.get(mock_request)

        assert response.status_code == 200
        payload = response.data
        assert payload["name"] == "Test Service"
        assert payload["status"] == Status.OK.value
        assert payload["message"] == "Service is operational"
        assert payload["latency_ms"] >= 0
        assert payload["timestamp"] == "2023-01-01T00:00:00+00:00"

    @patch("goats_tom.api_views.status.mixins.base.datetime")
    def test_get_missing_credentials(self, mock_datetime, mixin, mock_request):
        # Mock datetime to ensure consistent timestamps
        mock_datetime.now.return_value = datetime(2023, 1, 1, tzinfo=timezone.utc)

        # Override get_credentials to raise MissingCredentialsError
        def mock_get_credentials(request):
            raise MissingCredentialsError()

        mixin.get_credentials = mock_get_credentials

        response = mixin.get(mock_request)

        assert response.status_code == 200
        payload = response.data
        assert payload["name"] == "Test Service"
        assert payload["status"] == Status.WARNING.value
        assert payload["message"] == "Missing credentials for Test Service"
        assert payload["latency_ms"] == 0.0
        assert payload["timestamp"] == "2023-01-01T00:00:00+00:00"

    @patch("goats_tom.api_views.status.mixins.base.datetime")
    def test_get_service_exception(self, mock_datetime, mixin, mock_request):
        # Mock datetime to ensure consistent timestamps
        mock_datetime.now.return_value = datetime(2023, 1, 1, tzinfo=timezone.utc)

        # Override check_service to raise an exception
        def mock_check_service(credentials, *args, **kwargs):
            raise Exception("Service failure")

        mixin.check_service = mock_check_service

        response = mixin.get(mock_request)

        assert response.status_code == 200
        payload = response.data
        assert payload["name"] == "Test Service"
        assert payload["status"] == Status.DOWN.value
        assert payload["message"] == "Service failure"
        assert payload["latency_ms"] >= 0
        assert payload["timestamp"] == "2023-01-01T00:00:00+00:00"

def test_register_status_decorator():
    status_mixins.clear()

    @register_status("test", "Test Service")
    class DummyStatusMixin(BaseStatusMixin):
        pass

    assert "test" in status_mixins
    entry = status_mixins["test"]
    assert entry["display_name"] == "Test Service"
    assert entry["endpoint"] == "/status/test/"
    assert isinstance(entry["instance"], DummyStatusMixin)

def test_register_status_duplicate_raises():
    status_mixins.clear()

    @register_status("duplicate", "First Service")
    class FirstStatusMixin(BaseStatusMixin):
        pass

    with pytest.raises(ValueError, match="Service 'duplicate' is already registered."):
        @register_status("duplicate", "Second Service")
        class SecondStatusMixin(BaseStatusMixin):
            pass
