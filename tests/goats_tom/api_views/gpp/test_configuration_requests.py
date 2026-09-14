from unittest.mock import AsyncMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPConfigurationRequestViewSet
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.django_db
class TestGPPConfigurationRequestViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.list_view = GPPConfigurationRequestViewSet.as_view({"get": "list"})
        self.url = "/api/gpp/configuration-requests/"
        self.configuration_request = {
            "id": "cr-1",
            "status": "APPROVED",
            "justification": "Bright transient follow-up.",
            "applicableObservations": ["o-1"],
            "configuration": {
                "conditions": {
                    "imageQuality": "POINT_ONE",
                    "cloudExtinction": "POINT_ONE",
                    "skyBackground": "DARKEST",
                    "waterVapor": "VERY_DRY",
                },
                "target": None,
                "observingMode": {
                    "instrument": "GMOS_NORTH",
                    "mode": "GMOS_NORTH_LONG_SLIT",
                    "gmosNorthLongSlit": {"grating": "B1200_G5301"},
                },
            },
        }

        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_list_success(self, mocker):
        client = mocker.patch(
            "goats_tom.api_views.gpp.configuration_requests.GPPClient"
        ).return_value
        payload = mocker.Mock()
        payload.model_dump.return_value = {
            "configurationRequests": {
                "matches": [self.configuration_request],
                "hasMore": False,
            }
        }
        client.goats.get_configuration_requests_by_program_id = AsyncMock(
            return_value=payload
        )

        request = self.factory.get(self.url, {"program_id": "p-1"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["matches"] == [self.configuration_request]
        assert response.data["hasMore"] is False
        client.goats.get_configuration_requests_by_program_id.assert_called_once_with(
            program_id="p-1"
        )

    def test_list_missing_gpplogin(self):
        request = self.factory.get(self.url, {"program_id": "p-1"})
        force_authenticate(request, user=self.user_without_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_list_missing_program_id(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "A 'program_id' query parameter is required."

    def test_list_handles_client_exception(self, mocker):
        client = mocker.patch(
            "goats_tom.api_views.gpp.configuration_requests.GPPClient"
        ).return_value
        client.goats.get_configuration_requests_by_program_id = AsyncMock(
            side_effect=RuntimeError("backend down")
        )

        request = self.factory.get(self.url, {"program_id": "p-1"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "backend down"
