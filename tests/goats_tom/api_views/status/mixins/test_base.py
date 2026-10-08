import pytest
from unittest.mock import MagicMock, patch
from rest_framework.response import Response
from rest_framework.request import Request
from datetime import datetime, timezone

from goats_tom.service_checks import CheckResult
from goats_tom.api_views.status.mixins.base import (
    BaseStatusMixin,
    Credentials,
    Status,
    StatusPayload,
    MissingCredentialsError,
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
                    return CheckResult(True, "Service is operational")
                return CheckResult(False, "Invalid credentials")

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
        assert payload["credentials"] == Credentials.VERIFIED.value
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
        # No public URL: availability cannot be told without credentials.
        assert payload["status"] == Status.UNKNOWN.value
        assert payload["credentials"] == Credentials.MISSING.value
        assert payload["message"] == "No credentials stored."
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
        assert payload["status"] == Status.UNKNOWN.value
        assert payload["credentials"] == Credentials.UNCHECKED.value
        # The error itself is only logged.
        assert payload["message"] == "Test Service could not be checked."
        assert payload["latency_ms"] >= 0
        assert payload["timestamp"] == "2023-01-01T00:00:00+00:00"

class TestStatusCache:
    """Checks made with a user's credentials are reused for a while."""

    @pytest.fixture
    def mixin(self):
        class CountingMixin(BaseStatusMixin):
            service_name = "Counting"
            calls = 0

            def get_credentials(self, request):
                return {"token": request.token}

            def check_service(self, credentials, *args, **kwargs):
                type(self).calls += 1
                return CheckResult(True, "fine")

        return CountingMixin()

    @pytest.fixture(autouse=True)
    def locmem_cache(self, settings):
        settings.CACHES = {
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        }
        from django.core.cache import cache

        cache.clear()

    def _request(self, token="t", refresh=None, pk=1):
        request = MagicMock(spec=Request)
        request.user = MagicMock(pk=pk)
        request.token = token
        request.query_params = {"refresh": refresh} if refresh else {}
        return request

    def test_second_check_is_cached(self, mixin):
        first = mixin.get(self._request())
        second = mixin.get(self._request())

        assert type(mixin).calls == 1
        assert second.data == first.data

    def test_refresh_skips_cache(self, mixin):
        mixin.get(self._request())
        mixin.get(self._request(refresh="1"))

        assert type(mixin).calls == 2

    def test_new_credentials_are_checked_again(self, mixin):
        mixin.get(self._request(token="old"))
        mixin.get(self._request(token="new"))

        assert type(mixin).calls == 2

    def test_users_do_not_share_results(self, mixin):
        mixin.get(self._request(pk=1))
        mixin.get(self._request(pk=2))

        assert type(mixin).calls == 2


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
    assert entry["group"] == "account"
    assert entry["url"] is None
    assert entry["url_label"] is None
    assert entry["manage_url_name"] is None

def test_register_status_duplicate_raises():
    status_mixins.clear()

    @register_status("duplicate", "First Service")
    class FirstStatusMixin(BaseStatusMixin):
        pass

    with pytest.raises(ValueError, match="Service 'duplicate' is already registered."):
        @register_status("duplicate", "Second Service")
        class SecondStatusMixin(BaseStatusMixin):
            pass


def test_inconclusive_credential_check_keeps_service_available():
    result = CheckResult(False, "API check failed", verified=False)
    state, credentials, message = BaseStatusMixin()._result_state(result)
    assert state == Status.OK
    assert credentials == Credentials.UNCHECKED
    assert message == "API check failed"


def test_inconclusive_availability_is_unknown():
    result = CheckResult(False, "Not found", reachable=None, verified=False)
    state, credentials, _ = BaseStatusMixin()._result_state(result)
    assert state == Status.UNKNOWN
    assert credentials == Credentials.UNCHECKED


def test_inconclusive_availability_without_credentials_is_unknown():
    mixin = BaseStatusMixin()
    mixin.check_public = lambda: CheckResult(False, "Not found", reachable=None, verified=False)
    state, credentials, _ = mixin._missing_state()
    assert state == Status.UNKNOWN
    assert credentials == Credentials.MISSING


def test_public_http_error_maps_to_unknown():
    mixin = BaseStatusMixin()
    mixin.uses_credentials = False
    state, credentials, _ = mixin._result_state(CheckResult(False, "HTTP 429", verified=False))
    assert state == Status.UNKNOWN
    assert credentials is None


def test_empty_and_missing_credentials_use_distinct_cached_results(settings):
    from django.core.cache import cache
    from unittest.mock import Mock
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    mixin = BaseStatusMixin()
    mixin.get_public_url = Mock(return_value="https://example.test")
    mixin.get_credentials = Mock(return_value={})
    mixin.check_service = Mock(return_value=CheckResult(True, "up", verified=False))
    request = Mock(user=Mock(pk=1), query_params={})
    mixin.get(request)
    mixin.get(request)
    mixin.check_service.assert_called_once()
    mixin.get_credentials.side_effect = MissingCredentialsError
    with patch("goats_tom.api_views.status.mixins.base.check_reachable", return_value=CheckResult(True, "up")) as probe:
        assert mixin.get(request).data["credentials"] == "missing"
        assert mixin.get(request).data["credentials"] == "missing"
        probe.assert_called_once()


def test_unexpected_error_text_is_never_logged(caplog):
    from unittest.mock import Mock
    mixin = BaseStatusMixin()
    mixin.get_credentials = Mock(side_effect=RuntimeError("PRIVATE_TEST_TOKEN"))
    response = mixin.get(Mock())
    assert response.data["status"] == "unknown"
    assert "PRIVATE_TEST_TOKEN" not in caplog.text
