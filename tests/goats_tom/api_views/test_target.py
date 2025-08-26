import pytest
from unittest.mock import patch
from astropy.table import Table
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from guardian.shortcuts import assign_perm
from goats_tom.api_views.target import TargetViewSet
from goats_tom.tests.factories import UserFactory, GOALoginFactory
from tom_targets.tests.factories import SiderealTargetFactory
from django.urls import reverse


@pytest.mark.django_db
class TestObservationsInRadius:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.view = TargetViewSet.as_view({"get": "observations_in_radius"})

        self.user_with_login = UserFactory()
        GOALoginFactory(user=self.user_with_login)
        self.target = SiderealTargetFactory()
        assign_perm("view_target", self.user_with_login, self.target)
        self.user_without_login = UserFactory()
        self.url = reverse("targets-observations-in-radius", kwargs={"pk": self.target.id})


    def test_missing_goa_login_returns_400(self):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_without_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "GOA login credentials" in response.data["detail"]

    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=False)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_invalid_credentials_returns_400(self, mock_login, mock_authenticated):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not valid" in response.data["detail"]

    @patch("goats_tom.api_views.target.GOA.query_raw", side_effect=Exception("Error"))
    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=True)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_query_exception_returns_500(self, mock_login, mock_authenticated, mock_query_raw):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Error during GOA query" in response.data["detail"]

    @patch("goats_tom.api_views.target.GOA.query_raw", return_value=None)
    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=True)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_query_returns_none(self, mock_login, mock_authenticated, mock_query_raw):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["observation_ids"] == []

    @patch("goats_tom.api_views.target.GOA.query_raw", return_value=Table())
    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=True)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_query_returns_empty_table(self, mock_login, mock_authenticated, mock_query_raw):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["observation_ids"] == []

    @patch("goats_tom.api_views.target.GOA.query_raw", return_value=Table(names=["not_id"], rows=[[1]]))
    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=True)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_query_missing_observation_id(self, mock_login, mock_authenticated, mock_query_raw):
        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["observation_ids"] == []

    @patch("goats_tom.api_views.target.GOA.query_raw")
    @patch("goats_tom.api_views.target.GOA.authenticated", return_value=True)
    @patch("goats_tom.api_views.target.GOA.login")
    def test_successful_query(self, mock_login, mock_authenticated, mock_query_raw):
        table = Table(names=["observation_id"], rows=[[1], [2], [1], [None]])
        mock_query_raw.return_value = table

        request = self.factory.get(self.url)
        force_authenticate(request, user=self.user_with_login)

        response = self.view(request, pk=self.target.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["observation_ids"] == [1, 2]
