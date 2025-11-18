from unittest.mock import AsyncMock

import pytest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPObservationViewSet
from goats_tom.api_views.gpp.observations import (
    MessageStatus,
    ResponseStatus,
    Stage,
    StageMessage,
    build_failure_response,
)
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.parametrize(
    "stage, error, previous_messages, data, http_status, overall_status, expected_response",
    [
        (
            Stage.VALIDATION,
            "Validation error occurred",
            [],
            None,
            status.HTTP_400_BAD_REQUEST,
            ResponseStatus.FAILURE,
            {
                "status": "Failure",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Error",
                        "message": "Validation error occurred",
                    }
                ],
                "data": {},
            },
        ),
        (
            Stage.CREATE_OBSERVATION,
            Exception("Unexpected error"),
            [
                StageMessage(
                    stage=Stage.CREDENTIALS_CHECK,
                    status=MessageStatus.SUCCESS,
                    message="Credentials verified successfully.",
                )
            ],
            {"key": "value"},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ResponseStatus.FAILURE,
            {
                "status": "Failure",
                "messages": [
                    {
                        "stage": "Credentials Check",
                        "status": "Success",
                        "message": "Credentials verified successfully.",
                    },
                    {
                        "stage": "Create Observation",
                        "status": "Error",
                        "message": "Unexpected error",
                    },
                ],
                "data": {"key": "value"},
            },
        ),
        (
            Stage.UPDATE_TARGET,
            "Target update failed",
            [
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message="Validation passed.",
                )
            ],
            None,
            status.HTTP_400_BAD_REQUEST,
            ResponseStatus.PARTIAL_SUCCESS,
            {
                "status": "Partial Success",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Success",
                        "message": "Validation passed.",
                    },
                    {
                        "stage": "Update Sidereal Target",
                        "status": "Error",
                        "message": "Target update failed",
                    },
                ],
                "data": {},
            },
        ),
    ],
)
def test_build_failure_response(
    stage,
    error,
    previous_messages,
    data,
    http_status,
    overall_status,
    expected_response,
):
    response = build_failure_response(
        stage=stage,
        error=error,
        previous_messages=previous_messages,
        data=data,
        http_status=http_status,
        overall_status=overall_status,
    )

    assert isinstance(response, Response)
    assert response.status_code == http_status
    assert response.data == expected_response


@pytest.mark.django_db
class TestGPPObservationViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.viewset = GPPObservationViewSet()
        self.list_view = GPPObservationViewSet.as_view({"get": "list"})
        self.retrieve_view = GPPObservationViewSet.as_view({"get": "retrieve"})
        self.create_and_save_view = GPPObservationViewSet.as_view(
            {"post": "create_and_save_observation"}
        )

        self.observation_id = "o-23e1"
        self.observation_data = {"observation_id": self.observation_id, "name": "m27"}
        self.observations_url = "/api/gpp/observations/"
        self.observation_detail_url = f"/api/gpp/observations/{self.observation_id}/"
        self.observation_save_only_url = f"{self.observations_url}save-only/"
        self.observation_create_and_save_url = (
            f"{self.observations_url}create-and-save/"
        )
        self.observation_update_and_save_url = (
            f"{self.observations_url}update-and-save/"
        )

        # Setup users.
        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_create_and_save_missing_gpplogin(self) -> None:
        """Return 400 if the user has no GPP credentials."""
        request = self.factory.post(self.observation_create_and_save_url, {})
        force_authenticate(request, user=self.user_without_login)

        response = self.create_and_save_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_observations_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_all = AsyncMock(
            return_value=[self.observation_data]
        )

        request = self.factory.get(self.observations_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == [self.observation_data]
        mock_client.return_value.observation.get_all.assert_called_once()

    def test_list_observations_missing_gpplogin(self):
        request = self.factory.get(self.observations_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_retrieve_observation_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_by_id = AsyncMock(
            return_value=self.observation_data
        )

        request = self.factory.get(self.observation_detail_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.retrieve_view(request, pk=self.observation_id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == self.observation_data
        mock_client.return_value.observation.get_by_id.assert_called_once_with(
            observation_id=self.observation_id
        )

    def test_retrieve_observation_missing_gpplogin(self):
        request = self.factory.get(self.observation_detail_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.retrieve_view(request, pk=self.observation_id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_too_observation(self):
        obs = {
            "targetEnvironment": {
                "asterism": [
                    {"id": "t-1", "opportunity": {"__typename": "Opportunity"}}
                ]
            }
        }
        assert self.viewset.is_too(obs) is True

    def test_normal_observation_opportunity_none(self):
        obs = {"targetEnvironment": {"asterism": [{"id": "t-2", "opportunity": None}]}}
        assert self.viewset.is_too(obs) is False

    def test_empty_asterism_list(self):
        obs = {"targetEnvironment": {"asterism": []}}
        assert self.viewset.is_too(obs) is False

    def test_missing_asterism_key(self):
        obs = {"targetEnvironment": {}}
        assert self.viewset.is_too(obs) is False

    def test_asterism_none(self):
        obs = {"targetEnvironment": {"asterism": None}}
        assert self.viewset.is_too(obs) is False

    def test_missing_target_environment(self):
        obs = {}
        assert self.viewset.is_too(obs) is False

    def test_target_environment_none(self):
        obs = {"targetEnvironment": None}
        assert self.viewset.is_too(obs) is False
