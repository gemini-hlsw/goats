import pytest
from unittest.mock import AsyncMock, Mock, patch
from django.conf import settings
from rest_framework.request import Request
from goats_tom.api_views.status.mixins.gpp import GPPStatusMixin, MissingCredentialsError
from goats_tom.api_views.status.mixins.base import Status

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

    with pytest.raises(MissingCredentialsError, match="Missing GPP login credentials"):
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
    """check_service returns OK when the GPP client reports reachable."""
    credentials = {"token": "test_token", "env": "DEVELOPMENT"}
    with patch("goats_tom.api_views.status.mixins.gpp.GPPClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.ping = AsyncMock(return_value=(True, None))

        mixin = GPPStatusMixin()
        status, message = mixin.check_service(credentials)

    assert status == Status.OK
    assert message == "GPP service is reachable."
    mock_client_cls.assert_called_once_with(token="test_token")


def test_check_service_unreachable():
    """check_service returns DOWN with the error message when ping fails."""
    credentials = {"token": "test_token", "env": "DEVELOPMENT"}
    with patch("goats_tom.api_views.status.mixins.gpp.GPPClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.ping = AsyncMock(return_value=(False, "boom"))

        mixin = GPPStatusMixin()
        status, message = mixin.check_service(credentials)

    assert status == Status.DOWN
    assert message == "GPP service is unreachable: boom"
