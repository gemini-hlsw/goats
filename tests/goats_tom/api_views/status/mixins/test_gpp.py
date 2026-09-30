import pytest
from unittest.mock import AsyncMock, Mock, patch
from django.conf import settings
from rest_framework.request import Request
from goats_tom.api_views.status.mixins.gpp import GPPStatusMixin, MissingCredentialsError
from goats_tom.service_checks import CheckResult

@pytest.fixture
def mock_request():
    """Fixture to create a mock request object."""
    request = Mock(spec=Request)
    request.user = Mock()
    return request


def test_get_credentials_success(mock_request):
    """Test get_credentials when credentials are present and valid."""
    mock_request.user.gpplogin = Mock(token="test_token")
    with patch.object(settings, "GPP_ENV", "DEVELOPMENT"):
        mixin = GPPStatusMixin()
        credentials = mixin.get_credentials(mock_request)

    assert credentials == {
        "token": "test_token",
        "env": "DEVELOPMENT",
    }


def test_get_credentials_missing_gpplogin(mock_request):
    """Test get_credentials when gpplogin attribute is missing."""
    del mock_request.user.gpplogin
    mixin = GPPStatusMixin()

    with pytest.raises(MissingCredentialsError, match="No GPPLogin credentials"):
        mixin.get_credentials(mock_request)


def test_get_credentials_missing_gpp_env(mock_request):
    """Test get_credentials when GPP_ENV is missing in settings."""
    mock_request.user.gpplogin = Mock(token="test_token")
    with patch.object(settings, "GPP_ENV", None):
        mixin = GPPStatusMixin()

        with pytest.raises(
            MissingCredentialsError, match="Missing GPP environment in settings"
        ):
            mixin.get_credentials(mock_request)


def test_check_service_reachable():
    """check_service reports the token accepted when the ping succeeds."""
    credentials = {"token": "test_token", "env": "DEVELOPMENT"}
    with patch("goats_tom.service_checks.GPPClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.close = AsyncMock()
        mock_client.graphql.__aenter__.return_value = mock_client.graphql
        mock_client.graphql.ping = AsyncMock(return_value=None)

        mixin = GPPStatusMixin()
        result = mixin.check_service(credentials)

    assert result == CheckResult(True, "GPP accepted the token.")
    mock_client_cls.assert_called_once_with(token="test_token", debug=False)


def test_check_service_unreachable():
    """check_service reports GPP unavailable when neither ping nor server answer."""
    credentials = {"token": "test_token", "env": "DEVELOPMENT"}
    with (
        patch("goats_tom.service_checks.GPPClient") as mock_client_cls,
        patch(
            "goats_tom.service_checks.check_reachable",
            return_value=CheckResult(False, "GPP is not available.", reachable=False),
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.close = AsyncMock()
        mock_client.graphql.__aenter__.return_value = mock_client.graphql
        mock_client.graphql.ping = AsyncMock(side_effect=RuntimeError("network"))

        mixin = GPPStatusMixin()
        result = mixin.check_service(credentials)

    assert result == CheckResult(False, "GPP is not available.", reachable=False)


def test_public_url_needs_no_token():
    with patch("goats_tom.api_views.status.mixins.gpp.GPPSettings") as mock_settings:
        mock_settings.return_value.environment.base_url = "https://gpp.example"

        assert GPPStatusMixin().get_public_url() == "https://gpp.example"
