import pytest
from unittest.mock import Mock, patch
from django.conf import settings
from rest_framework.request import Request
from goats_tom.api_views.status.mixins.gpp import GPPStatusMixin, MissingCredentialsError

@pytest.fixture
def mock_request():
    """Fixture to create a mock request object."""
    request = Mock(spec=Request)
    request.user = Mock()
    return request


def test_get_credentials_success(mock_request):
    """Test get_credentials when credentials are present and valid."""
    mock_request.user.gpplogin = Mock(token="test_token")
    with patch.object(settings, "GPP_URL", "https://example.com"):
        mixin = GPPStatusMixin()
        credentials = mixin.get_credentials(mock_request)

    assert credentials == {
        "token": "test_token",
        "url": "https://example.com",
    }


def test_get_credentials_missing_gpplogin(mock_request):
    """Test get_credentials when gpplogin attribute is missing."""
    del mock_request.user.gpplogin
    mixin = GPPStatusMixin()

    with pytest.raises(MissingCredentialsError, match="Missing GPP login credentials"):
        mixin.get_credentials(mock_request)


def test_get_credentials_missing_gpp_url(mock_request):
    """Test get_credentials when GPP_URL is missing in settings."""
    mock_request.user.gpplogin = Mock(token="test_token")
    with patch.object(settings, "GPP_URL", None):
        mixin = GPPStatusMixin()

        with pytest.raises(
            MissingCredentialsError, match="Missing GPP URL in settings"
        ):
            mixin.get_credentials(mock_request)
