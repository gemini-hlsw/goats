import json
from unittest.mock import AsyncMock, Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from gpp_client.generated.enums import ObservationWorkflowState
from gpp_client.generated.set_observation_workflow_state import (
    SetObservationWorkflowStateSetObservationWorkflowState,
)
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


def _mock_workflow_state_result(
    state: ObservationWorkflowState | str,
) -> Mock:
    """Mock the Pydantic workflow state model returned by gpp-client.

    Uses ``spec`` so renames or removed fields on the real model surface as
    test failures instead of silently passing.
    """
    if isinstance(state, str):
        state = ObservationWorkflowState(state)
    mock = Mock(spec=SetObservationWorkflowStateSetObservationWorkflowState)
    mock.state = state
    return mock


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

    def test_create_and_save_validation_failure(self, mocker):
        """Validation error returns Failure response without touching GPP client."""
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        )
        mock_serializer.return_value.is_valid.side_effect = ValueError("bad data")

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        view = GPPObservationViewSet.as_view(
            {"post": "create_and_save_observation"}
        )
        response = view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        stages = [m["stage"] for m in response.data["messages"]]
        assert "Data Validation" in stages
        # GPP client was instantiated but no API calls were made past validation.
        mock_client.assert_called_once()

    def test_update_only_missing_gpplogin(self):
        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(self.observation_update_and_save_url, {})
        force_authenticate(request, user=self.user_without_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        assert response.data["messages"][0]["stage"] == "Credentials Check"

    def test_update_only_validation_failure(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        )
        mock_serializer.return_value.is_valid.side_effect = ValueError("bad data")

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        stages = [m["stage"] for m in response.data["messages"]]
        assert "Data Validation" in stages
        mock_client.assert_called_once()

    def test_save_observation_only_validation_failure(self, mocker):
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        )
        mock_serializer.return_value.is_valid.side_effect = ValueError("bad data")

        save_view = GPPObservationViewSet.as_view({"post": "save_observation_only"})
        request = self.factory.post(self.observation_save_only_url, {})
        force_authenticate(request, user=self.user_with_login)

        response = save_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        stages = [m["stage"] for m in response.data["messages"]]
        assert "Data Validation" in stages

    def _mock_validated_serializers(self, mocker, with_instrument=False):
        """Patch serializers used in update/create flows to return valid objects."""
        goats_target = mocker.Mock()
        goats_target.id = 99
        goats_target.name = "test-target"

        context = mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        )
        context_inst = context.return_value
        context_inst.is_valid.return_value = True
        context_inst.gpp_target_id = "t-1"
        context_inst.gpp_observation_id = "o-1"
        context_inst.gpp_program_id = "p-1"
        context_inst.goats_target = goats_target
        if with_instrument:
            context_inst.instrument = "GMOS_SOUTH_LONG_SLIT"
            context_inst.format_observation.return_value = {
                "reference": {"label": "obs-ref"}
            }

        target_ser = mocker.patch(
            "goats_tom.api_views.gpp.observations.TargetSerializer"
        )
        target_props = mocker.Mock()
        target_ser.return_value.is_valid.return_value = True
        target_ser.return_value.to_pydantic.return_value = target_props

        obs_ser = mocker.patch(
            "goats_tom.api_views.gpp.observations.ObservationSerializer"
        )
        obs_props = mocker.Mock()
        obs_ser.return_value.is_valid.return_value = True
        obs_ser.return_value.to_pydantic.return_value = obs_props

        workflow_ser = mocker.patch(
            "goats_tom.api_views.gpp.observations.WorkflowStateSerializer"
        )
        workflow_ser.return_value.is_valid.return_value = True
        workflow_ser.return_value.workflow_state_enum = "INACTIVE"

        return goats_target, target_props, obs_props

    def test_update_only_happy_path(self, mocker):
        """Exercise update_only target/observation/workflow updates."""
        self._mock_validated_serializers(mocker)

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        target_update_result = mocker.Mock()
        target_update_result.model_dump.return_value = {
            "updateTargets": {"targets": [{"id": "t-updated"}]}
        }
        client.target.update_by_id = AsyncMock(return_value=target_update_result)

        obs_update_result = mocker.Mock()
        obs_update_result.model_dump.return_value = {
            "updateObservations": {"observations": [{"id": "o-updated"}]}
        }
        client.observation.update_by_id = AsyncMock(return_value=obs_update_result)

        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "Success"
        assert response.data["data"]["updatedTargetId"] == "t-updated"
        assert response.data["data"]["updatedObservationId"] == "o-updated"
        client.target.update_by_id.assert_called_once()
        client.observation.update_by_id.assert_called_once()
        client.workflow_state.update_by_id_with_retry.assert_called_once()

    def test_update_only_target_update_returns_no_id(self, mocker):
        """update_only treats missing target id as a partial failure but continues."""
        self._mock_validated_serializers(mocker)

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        target_update_result = mocker.Mock()
        target_update_result.model_dump.return_value = {
            "updateTargets": {"targets": []}
        }
        client.target.update_by_id = AsyncMock(return_value=target_update_result)

        obs_update_result = mocker.Mock()
        obs_update_result.model_dump.return_value = {
            "updateObservations": {"observations": [{"id": "o-updated"}]}
        }
        client.observation.update_by_id = AsyncMock(return_value=obs_update_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        # Partial success because target update reported an error.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Partial Success"
        stages = {m["stage"]: m["status"] for m in response.data["messages"]}
        assert stages["Update Sidereal Target"] == "Error"
        assert stages["Update Observation"] == "Success"

    def test_create_and_save_happy_path(self, mocker):
        """Exercise the full create_and_save flow with mocked serializers."""
        goats_target, target_props, obs_props = self._mock_validated_serializers(
            mocker, with_instrument=True
        )
        # CloneObservationInput is a pydantic model that rejects Mock objects for
        # `set_`, so stub it out — observation_properties comes from a mocked
        # serializer.
        mocker.patch(
            "goats_tom.api_views.gpp.observations.CloneObservationInput"
        )

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        clone_target_result = mocker.Mock()
        clone_target_result.model_dump.return_value = {
            "cloneTarget": {"newTarget": {"id": "t-new"}}
        }
        client.target.clone = AsyncMock(return_value=clone_target_result)

        clone_obs_result = mocker.Mock()
        clone_obs_result.model_dump.return_value = {
            "cloneObservation": {
                "newObservation": {
                    "id": "o-new",
                    "reference": {"label": "obs-ref-new"},
                }
            }
        }
        client.observation.clone = AsyncMock(return_value=clone_obs_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        # Skip the GOATS save step — it uses the TOM viewset that requires DB state.
        mocker.patch.object(
            GPPObservationViewSet,
            "_create_goats_observation",
            return_value=Response(
                {"id": 1}, status=status.HTTP_201_CREATED
            ),
        )

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = self.create_and_save_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "Success"
        assert response.data["data"]["newTargetId"] == "t-new"
        assert response.data["data"]["newObservationId"] == "o-new"
        client.target.clone.assert_called_once()
        client.observation.clone.assert_called_once()

    def test_update_only_skips_finder_charts_processing_when_empty(self, mocker):
        """No _process_finder_charts call when toAdd/toDelete are empty."""
        self._mock_validated_serializers(mocker)
        spy = mocker.spy(GPPObservationViewSet, "_process_finder_charts")

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        target_update_result = mocker.Mock()
        target_update_result.model_dump.return_value = {
            "updateTargets": {"targets": [{"id": "t-updated"}]}
        }
        client.target.update_by_id = AsyncMock(return_value=target_update_result)

        obs_update_result = mocker.Mock()
        obs_update_result.model_dump.return_value = {
            "updateObservations": {"observations": [{"id": "o-updated"}]}
        }
        client.observation.update_by_id = AsyncMock(return_value=obs_update_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": json.dumps({"toAdd": [], "toDelete": []})},
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert spy.call_count == 0

    def test_update_only_processes_finder_charts_when_to_delete_present(
        self, mocker
    ):
        """_process_finder_charts is invoked when toDelete is non-empty."""
        self._mock_validated_serializers(mocker)
        spy = mocker.patch.object(
            GPPObservationViewSet,
            "_process_finder_charts",
            return_value=["existing-1"],
        )

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        target_update_result = mocker.Mock()
        target_update_result.model_dump.return_value = {
            "updateTargets": {"targets": [{"id": "t-updated"}]}
        }
        client.target.update_by_id = AsyncMock(return_value=target_update_result)

        obs_update_result = mocker.Mock()
        obs_update_result.model_dump.return_value = {
            "updateObservations": {"observations": [{"id": "o-updated"}]}
        }
        client.observation.update_by_id = AsyncMock(return_value=obs_update_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": json.dumps({"toAdd": [], "toDelete": ["a-1"]})},
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        spy.assert_called_once()

    def test_update_only_workflow_state_missing_state_renders_unknown(
        self, mocker
    ):
        """Workflow stage message degrades to 'unknown' when state is absent."""
        self._mock_validated_serializers(mocker)

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        target_update_result = mocker.Mock()
        target_update_result.model_dump.return_value = {
            "updateTargets": {"targets": [{"id": "t-updated"}]}
        }
        client.target.update_by_id = AsyncMock(return_value=target_update_result)

        obs_update_result = mocker.Mock()
        obs_update_result.model_dump.return_value = {
            "updateObservations": {"observations": [{"id": "o-updated"}]}
        }
        client.observation.update_by_id = AsyncMock(return_value=obs_update_result)
        # Workflow result returns None as payload (matches the GPP missing-payload
        # path now propagated as the model attribute).
        client.workflow_state.update_by_id_with_retry = AsyncMock(return_value=None)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        stages = {m["stage"]: m["message"] for m in response.data["messages"]}
        assert stages["Update Workflow State"] == "Workflow state set to unknown."

    def test_create_and_save_clone_target_returns_no_id(self, mocker):
        """create_and_save fails fast when the cloned target has no id."""
        self._mock_validated_serializers(mocker, with_instrument=True)

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        clone_target_result = mocker.Mock()
        clone_target_result.model_dump.return_value = {
            "cloneTarget": {"newTarget": {}}
        }
        client.target.clone = AsyncMock(return_value=clone_target_result)

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = self.create_and_save_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        stages = [m["stage"] for m in response.data["messages"]]
        assert "Create Sidereal Target" in stages

    def test_list_observations_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_result = mocker.Mock()
        mock_result.model_dump.return_value = [self.observation_data]
        mock_client.return_value.observation.get_all = AsyncMock(return_value=mock_result)

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

    def test_list_observations_with_program_id_splits_too_and_normal(self, mocker):
        too_obs = {
            "id": "o-too",
            "targetEnvironment": {
                "asterism": [
                    {"id": "t-1", "opportunity": {"__typename": "Opportunity"}}
                ]
            },
        }
        normal_obs = {
            "id": "o-norm",
            "targetEnvironment": {
                "asterism": [{"id": "t-2", "opportunity": None}]
            },
        }
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_payload = mocker.Mock()
        mock_payload.model_dump.return_value = {
            "observations": {
                "matches": [too_obs, normal_obs],
                "hasMore": True,
            }
        }
        mock_client.return_value.goats.get_observations_by_program_id = AsyncMock(
            return_value=mock_payload
        )

        request = self.factory.get(self.observations_url, {"program_id": "p-1"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["matches"]["too"]["count"] == 1
        assert response.data["matches"]["too"]["results"] == [too_obs]
        assert response.data["matches"]["normal"]["count"] == 1
        assert response.data["matches"]["normal"]["results"] == [normal_obs]
        assert response.data["hasMore"] is True
        mock_client.return_value.goats.get_observations_by_program_id.assert_called_once_with(
            program_id="p-1"
        )

    def test_list_observations_handles_client_exception(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_all = AsyncMock(
            side_effect=RuntimeError("backend down")
        )

        request = self.factory.get(self.observations_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "backend down"

    def test_retrieve_observation_handles_client_exception(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_by_id = AsyncMock(
            side_effect=RuntimeError("not found")
        )

        request = self.factory.get(self.observation_detail_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.retrieve_view(request, pk=self.observation_id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "not found"

    def test_retrieve_observation_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_result = mocker.Mock()
        mock_result.model_dump.return_value = {"observation": self.observation_data}
        mock_client.return_value.observation.get_by_id = AsyncMock(return_value=mock_result)

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

    def test_normalize_finder_charts_without_payload_returns_empty_structure(self):
        data = {}

        out = self.viewset._normalize_finder_charts(data)

        assert out["finderCharts"] == {"toAdd": [], "toDelete": []}

    def test_normalize_finder_charts_builds_to_add_and_to_delete(self):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")
        file2 = SimpleUploadedFile("fc2.jpg", b"def", content_type="image/jpeg")

        data = {
            "finderCharts": json.dumps(
                {
                    "toAdd": [
                        {"fileKey": "fileA", "description": "first"},
                        {"fileKey": "fileB", "description": "second"},
                    ],
                    "toDelete": ["att-1", "att-2"],
                }
            ),
            "fileA": file1,
            "fileB": file2,
        }

        out = self.viewset._normalize_finder_charts(data)

        assert "fileA" not in out
        assert "fileB" not in out
        assert out["finderCharts"]["toDelete"] == ["att-1", "att-2"]

        to_add = out["finderCharts"]["toAdd"]
        assert len(to_add) == 2
        assert to_add[0]["description"] == "first"
        assert to_add[0]["file"] == file1
        assert to_add[1]["description"] == "second"
        assert to_add[1]["file"] == file2

    def test_normalize_finder_charts_skips_missing_file_objects(self):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")

        data = {
            "finderCharts": json.dumps(
                {
                    "toAdd": [
                        {"fileKey": "fileA", "description": "first"},
                        {"fileKey": "missingFile", "description": "missing"},
                    ],
                    "toDelete": [],
                }
            ),
            "fileA": file1,
        }

        out = self.viewset._normalize_finder_charts(data)

        to_add = out["finderCharts"]["toAdd"]
        assert len(to_add) == 1
        assert to_add[0]["description"] == "first"
        assert to_add[0]["file"] == file1

    def test_process_finder_charts_delete_only_returns_remaining_ids(self, mocker):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        mock_attachment_result = mocker.Mock()
        mock_attachment_result.model_dump.return_value = {
            "observation": {"attachments": [{"id": "a1"}, {"id": "a2"}]}
        }
        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation_id = mocker.Mock(
            return_value=mock_attachment_result
        )
        client.attachment.upload = mocker.Mock()

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": ["old-1", "old-2"],
                "toAdd": [],
            },
        )

        assert client.attachment.delete_by_id.call_count == 2
        client.attachment.delete_by_id.assert_any_call(attachment_id="old-1")
        client.attachment.delete_by_id.assert_any_call(attachment_id="old-2")
        client.attachment.get_all_by_observation_id.assert_called_once_with(
            observation_id="obs-1",
        )
        assert out == ["a1", "a2"]

    def test_process_finder_charts_add_only_uploads_and_appends_ids(self, mocker):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")
        file2 = SimpleUploadedFile("fc2.jpg", b"def", content_type="image/jpeg")

        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        mock_attachment_result = mocker.Mock()
        mock_attachment_result.model_dump.return_value = {
            "observation": {"attachments": [{"id": "existing-1"}]}
        }
        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation_id = mocker.Mock(
            return_value=mock_attachment_result
        )
        client.attachment.upload = mocker.Mock(side_effect=["new-1", "new-2"])

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "first", "file": file1},
                    {"description": "second", "file": file2},
                ],
            },
        )

        assert client.attachment.upload.call_count == 2

        first_call = client.attachment.upload.call_args_list[0]
        second_call = client.attachment.upload.call_args_list[1]

        assert first_call.kwargs["program_id"] == "prog-1"
        assert first_call.kwargs["file_name"] == "fc1.png"
        assert first_call.kwargs["description"] == "first"
        assert first_call.kwargs["content"] == b"abc"

        assert second_call.kwargs["file_name"] == "fc2.jpg"
        assert second_call.kwargs["description"] == "second"
        assert second_call.kwargs["content"] == b"def"

        assert out == ["existing-1", "new-1", "new-2"]

    def test_process_finder_charts_skips_items_without_file(self, mocker):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        mock_attachment_result = mocker.Mock()
        mock_attachment_result.model_dump.return_value = {
            "observation": {"attachments": [{"id": "existing-1"}]}
        }
        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation_id = mocker.Mock(
            return_value=mock_attachment_result
        )
        client.attachment.upload = mocker.Mock()

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "missing", "file": None},
                ],
            },
        )

        client.attachment.upload.assert_not_called()
        assert out == ["existing-1"]

    @pytest.mark.parametrize(
        "finder_charts, setup_attr, expected_pattern",
        [
            (
                {"toDelete": ["bad-id"], "toAdd": []},
                "delete_error",
                "Failed to delete finder chart 'bad-id'",
            ),
            (
                {"toDelete": [], "toAdd": []},
                "fetch_error",
                "Failed to fetch current finder charts",
            ),
            (
                {
                    "toDelete": [],
                    "toAdd": [
                        {
                            "description": "first",
                            "file": SimpleUploadedFile(
                                "fc1.png", b"abc", content_type="image/png"
                            ),
                        }
                    ],
                },
                "upload_error",
                "Failed to upload finder chart 'fc1.png'",
            ),
        ],
    )
    def test_process_finder_charts_raises_value_error(
        self, mocker, finder_charts, setup_attr, expected_pattern
    ):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        mock_attachment_result = mocker.Mock()
        mock_attachment_result.model_dump.return_value = {
            "observation": {"attachments": []}
        }
        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation_id = mocker.Mock(
            return_value=mock_attachment_result
        )
        client.attachment.upload = mocker.Mock()

        if setup_attr == "delete_error":
            client.attachment.delete_by_id.side_effect = RuntimeError("boom")
        elif setup_attr == "fetch_error":
            client.attachment.get_all_by_observation_id.side_effect = RuntimeError(
                "fetch failed"
            )
        elif setup_attr == "upload_error":
            client.attachment.upload.side_effect = RuntimeError("upload failed")

        with pytest.raises(ValueError, match=expected_pattern):
            self.viewset._process_finder_charts(
                client=client,
                observation_id="obs-1",
                program_id="prog-1",
                finder_charts=finder_charts,
            )
