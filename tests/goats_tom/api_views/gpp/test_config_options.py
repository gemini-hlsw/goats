from unittest.mock import AsyncMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPConfigOptionsViewSet
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.django_db
class TestGPPConfigOptionsViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.list_view = GPPConfigOptionsViewSet.as_view({"get": "list"})
        self.url = "/api/gpp/config-options/"
        self.spectroscopy_option = {
            "name": "GMOS-N B1200 0.50\"",
            "instrument": "GMOS_NORTH",
            "site": "GN",
            "focalPlane": "SINGLE_SLIT",
            "fpuLabel": "0.50\"",
            "disperserLabel": "B1200",
            "filterLabel": None,
            "slitWidth": {"arcseconds": 0.5},
            "resolution": 3744,
            "wavelengthMin": {"nanometers": 300.0},
            "wavelengthMax": {"nanometers": 700.0},
            "wavelengthOptimal": {"nanometers": 463.0},
            "wavelengthCoverage": {"nanometers": 164.0},
            "gmosNorth": {
                "fpu": "LONG_SLIT_0_50",
                "grating": "B1200_G5301",
                "filter": None,
            },
            "gmosSouth": None,
        }

        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_list_success(self, mocker):
        client = mocker.patch(
            "goats_tom.api_views.gpp.config_options.GPPClient"
        ).return_value
        payload = mocker.Mock()
        payload.model_dump.return_value = {
            "spectroscopyConfigOptions": [self.spectroscopy_option],
            "imagingConfigOptions": [],
        }
        client.goats.get_config_options = AsyncMock(return_value=payload)

        request = self.factory.get(self.url, {"instrument": "GMOS_NORTH"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["spectroscopy"] == [self.spectroscopy_option]
        assert response.data["imaging"] == []
        client.goats.get_config_options.assert_called_once_with(
            instrument="GMOS_NORTH"
        )

    def test_list_missing_gpplogin(self):
        request = self.factory.get(self.url, {"instrument": "GMOS_NORTH"})
        force_authenticate(request, user=self.user_without_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_list_missing_instrument(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "An 'instrument' query parameter is required."

    def test_list_unknown_instrument(self):
        request = self.factory.get(self.url, {"instrument": "TELESCOPIO"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "'TELESCOPIO' is not a known instrument."

    def test_list_handles_client_exception(self, mocker):
        client = mocker.patch(
            "goats_tom.api_views.gpp.config_options.GPPClient"
        ).return_value
        client.goats.get_config_options = AsyncMock(
            side_effect=RuntimeError("backend down")
        )

        request = self.factory.get(self.url, {"instrument": "GMOS_NORTH"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "backend down"
