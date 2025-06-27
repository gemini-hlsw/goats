import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from unittest.mock import AsyncMock

from goats_tom.tests.factories import UserFactory, GPPLoginFactory
from goats_tom.api_views import GPPProgramViewSet


@pytest.mark.django_db
class TestGPPProgramViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.list_view = GPPProgramViewSet.as_view({'get': 'list'})
        self.retrieve_view = GPPProgramViewSet.as_view({'get': 'retrieve'})

        self.program_id = "p-230e"
        self.program_data = {"program_id": self.program_id, "title": "Test Program"}
        self.programs_url = "/api/gpp/programs/"
        self.program_detail_url = f"/api/gpp/programs/{self.program_id}/"

        # Setup users.
        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_list_programs_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.programs.GPPClient")
        mock_client.return_value.program.get_all = AsyncMock(return_value=[self.program_data])

        request = self.factory.get(self.programs_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == [self.program_data]
        mock_client.return_value.program.get_all.assert_called_once()

    def test_list_programs_missing_gpplogin(self):
        request = self.factory.get(self.programs_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["detail"] == "GPP login credentials are not configured for this user."

    def test_retrieve_program_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.programs.GPPClient")
        mock_client.return_value.program.get_by_id = AsyncMock(return_value=self.program_data)

        request = self.factory.get(self.program_detail_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.retrieve_view(request, pk=self.program_id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == self.program_data
        mock_client.return_value.program.get_by_id.assert_called_once_with(program_id=self.program_id)

    def test_retrieve_program_missing_gpplogin(self):
        request = self.factory.get(self.program_detail_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.retrieve_view(request, pk=self.program_id)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["detail"] == "GPP login credentials are not configured for this user."