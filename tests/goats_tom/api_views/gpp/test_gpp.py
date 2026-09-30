from unittest.mock import AsyncMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPViewSet
from goats_tom.service_checks import CheckResult
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.django_db
class TestGPPViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.ping_view = GPPViewSet.as_view({"get": "ping"})
        self.ping_url = "/api/gpp/ping/"

        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_ping_missing_gpplogin(self):
        request = self.factory.get(self.ping_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.ping_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_ping_success(self, mocker):
        mock_client = mocker.patch("goats_tom.service_checks.GPPClient")
        mock_client.return_value.close = AsyncMock()
        mock_client.return_value.graphql.__aenter__.return_value = mock_client.return_value.graphql
        mock_client.return_value.graphql.ping = AsyncMock(return_value=None)

        request = self.factory.get(self.ping_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.ping_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"detail": "Successfully connected to GPP."}
        mock_client.assert_called_once()
        mock_client.return_value.graphql.ping.assert_called_once()

    def test_ping_unreachable(self, mocker):
        mock_client = mocker.patch("goats_tom.service_checks.GPPClient")
        mock_client.return_value.close = AsyncMock()
        mock_client.return_value.graphql.__aenter__.return_value = mock_client.return_value.graphql
        mock_client.return_value.graphql.ping = AsyncMock(side_effect=RuntimeError("network"))
        mocker.patch(
            "goats_tom.service_checks.check_reachable",
            return_value=CheckResult(True, "GPP is available."),
        )

        request = self.factory.get(self.ping_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.ping_view(request)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.data == {
            "detail": "The GPP credential check could not be completed. "
            "Please try again later."
        }
