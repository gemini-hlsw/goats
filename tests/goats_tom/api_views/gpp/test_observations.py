import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from gpp_client.exceptions import (
    GPPClientError,
    GPPWorkflowTransitionError,
    WorkflowReason,
)
from gpp_client.generated.enums import (
    AttachmentType,
    CalculationState,
    Existence,
    ObservationValidationCode,
    ObservationValidationCodeSeverity,
    ObservationWorkflowState,
)
from gpp_client.generated.exceptions import (
    GraphQLClientGraphQLError,
    GraphQLClientGraphQLMultiError,
)
from gpp_client.generated.set_observation_workflow_state import (
    SetObservationWorkflowStateSetObservationWorkflowState,
)
from httpx import ReadTimeout
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPObservationViewSet
from goats_tom.api_views.gpp.observations import (
    NOT_EDITABLE_REASON,
    LeftOutError,
    MessageStatus,
    ResponseStatus,
    Stage,
    StageMessage,
    apply_too_activation_labels,
    build_failure_response,
    build_goats_subtitle,
    failure_summary,
    left_out_error,
    normalize_discovery_survey,
    stage_error,
    state_error,
    summarize,
    summarize_calibration,
    workflow_report,
)
from goats_tom.tests.factories import GPPLoginFactory, UserFactory

CANNOT_EDIT_IFU = "GOATS cannot edit GMOS North IFU observations yet."
END_REQUIRED = "End must contain either 'atUtc' or 'after'."


def _multi_error(*messages: str, data: dict | None = None):
    """An answer from GPP with errors, as the client raises it."""
    return GraphQLClientGraphQLMultiError(
        errors=[GraphQLClientGraphQLError(message=m) for m in messages], data=data
    )


def _transition_error(reasons: list, allowed: tuple = ("INACTIVE",)):
    """A state GPP does not allow, as the client raises it."""
    return GPPWorkflowTransitionError(
        "Cannot change to INACTIVE.",
        requested="INACTIVE",
        allowed=list(allowed),
        reasons=reasons,
    )


def _observation(state, errors=(), dismissed=()):
    """An observation as ``get_by_id_when_ready`` returns it."""
    return SimpleNamespace(
        id="o-1",
        workflow=SimpleNamespace(
            value=SimpleNamespace(
                state=state,
                validation_errors=[
                    SimpleNamespace(code=code, severity=severity, messages=list(texts))
                    for code, severity, *texts in errors
                ],
            )
        ),
        program=SimpleNamespace(dismissed_warnings=list(dismissed)),
    )


def _answer(data: dict) -> Mock:
    """An answer from GPP, as the client returns it."""
    return Mock(model_dump=Mock(return_value=data))


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


def _workflow_read(
    state: ObservationWorkflowState,
    calculation: CalculationState = CalculationState.READY,
) -> SimpleNamespace:
    """The workflow of an observation, as ``workflow_state.get_by_id`` returns it."""
    return SimpleNamespace(
        observation=SimpleNamespace(
            workflow=SimpleNamespace(
                state=calculation, value=SimpleNamespace(state=state)
            )
        )
    )


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
                "summary": "Observation not sent to GPP",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Error",
                        "message": "Validation error occurred",
                        "details": [],
                        "label": "Not valid",
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
                "summary": "Observation not created",
                "messages": [
                    {
                        "stage": "Credentials Check",
                        "status": "Success",
                        "message": "Credentials verified successfully.",
                        "details": [],
                        "label": "",
                    },
                    {
                        "stage": "Create Observation",
                        "status": "Error",
                        "message": "Unexpected error",
                        "details": [],
                        "label": "Failed",
                    },
                ],
                "data": {"key": "value"},
            },
        ),
        (
            # Exceptions raised without a message (e.g. httpx.ReadTimeout) must
            # fall back to repr() instead of producing an empty message.
            Stage.CREATE_OBSERVATION,
            Exception(),
            [],
            None,
            status.HTTP_400_BAD_REQUEST,
            ResponseStatus.FAILURE,
            {
                "status": "Failure",
                "summary": "Observation not created",
                "messages": [
                    {
                        "stage": "Create Observation",
                        "status": "Error",
                        "message": "Exception()",
                        "details": [],
                        "label": "Failed",
                    }
                ],
                "data": {},
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
                "summary": "Observation not updated",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Success",
                        "message": "Validation passed.",
                        "details": [],
                        "label": "",
                    },
                    {
                        "stage": "Update Sidereal Target",
                        "status": "Error",
                        "message": "Target update failed",
                        "details": [],
                        "label": "Failed",
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


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("Rubin", "Rubin"),
        ("  Pan-STARRS  ", "Pan-STARRS"),
        # Colons delimit the subtitle fields, so they are stripped.
        ("Rubin: LSST", "Rubin LSST"),
        (123, ""),
    ],
)
def test_normalize_discovery_survey(raw, expected):
    assert normalize_discovery_survey(raw) == expected


@pytest.mark.parametrize(
    "discovery_survey, expected",
    [
        ("", "GOATS:1.2.3"),
        ("Rubin", "GOATS:1.2.3:Rubin"),
    ],
)
def test_build_goats_subtitle(mocker, discovery_survey, expected):
    mocker.patch(
        "goats_tom.api_views.gpp.observations.get_goats_version",
        return_value="1.2.3",
    )

    assert build_goats_subtitle(discovery_survey) == expected


def test_build_goats_subtitle_without_version(mocker):
    mocker.patch(
        "goats_tom.api_views.gpp.observations.get_goats_version",
        side_effect=RuntimeError("boom"),
    )

    assert build_goats_subtitle() == "GOATS"


@pytest.mark.parametrize(
    "activation, name, notes, expected_name, expected_notes",
    [
        (None, "SN 2026a", "Hi", "SN 2026a", "Hi"),
        ("NONE", "SN 2026a", "Hi", "SN 2026a", "Hi"),
        ("RAPID", "SN 2026a", None, "RAPID SN 2026a", "RAPID"),
        (
            "INTERRUPTING",
            "SN 2026a",
            "Hi",
            "INTERRUPTING SN 2026a",
            "INTERRUPTING\nHi",
        ),
        # Already labelled, so nothing is added twice.
        ("RAPID", "RAPID SN 2026a", "RAPID\nHi", "RAPID SN 2026a", "RAPID\nHi"),
    ],
)
def test_apply_too_activation_labels(
    activation, name, notes, expected_name, expected_notes
):
    target = SimpleNamespace(name=name)
    observation = SimpleNamespace(observer_notes=notes)

    apply_too_activation_labels(
        target, observation, {"tooActivationSelect": activation}
    )

    assert target.name == expected_name
    assert observation.observer_notes == expected_notes


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

        view = GPPObservationViewSet.as_view({"post": "create_and_save_observation"})
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
        assert response.data["summary"] == "Observation not sent to GPP"
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
        assert response.data["summary"] == "Observation not sent to GPP"
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
        # Saving in GOATS sends nothing to GPP in the first place.
        assert response.data["summary"] == "Observation not saved in GOATS"
        stages = [m["stage"] for m in response.data["messages"]]
        assert "Data Validation" in stages

    def test_save_observation_only_normalization_failure(self, mocker):
        mocker.patch.object(
            GPPObservationViewSet, "_normalize_form_data", side_effect=ValueError("bad")
        )

        save_view = GPPObservationViewSet.as_view({"post": "save_observation_only"})
        request = self.factory.post(self.observation_save_only_url, {})
        force_authenticate(request, user=self.user_with_login)

        response = save_view(request)

        assert response.data["status"] == "Failure"
        assert response.data["summary"] == "Observation not saved in GOATS"

    @pytest.mark.parametrize(
        "saved, expected_status, expected_summary",
        [
            (
                {"return_value": Response({"id": 1}, status=status.HTTP_201_CREATED)},
                "Success",
                "Observation saved in GOATS",
            ),
            (
                {
                    "return_value": Response(
                        {"detail": "Exists."}, status=status.HTTP_208_ALREADY_REPORTED
                    )
                },
                "Partial Success",
                "Observation already in GOATS",
            ),
            (
                {"side_effect": ValueError("boom")},
                "Failure",
                "Observation not saved in GOATS",
            ),
        ],
        ids=["saved", "already saved", "not saved"],
    )
    def test_save_observation_only_says_what_happened(
        self, mocker, saved, expected_status, expected_summary
    ):
        self._mock_validated_serializers(mocker, with_instrument=True)
        mocker.patch.object(GPPObservationViewSet, "_create_goats_observation", **saved)

        save_view = GPPObservationViewSet.as_view({"post": "save_observation_only"})
        request = self.factory.post(self.observation_save_only_url, {})
        force_authenticate(request, user=self.user_with_login)

        response = save_view(request)

        assert response.data["status"] == expected_status
        assert response.data["summary"] == expected_summary
        # No other step says which one it is.
        said = {
            "Success": "o-1 saved",
            "Partial Success": "o-1 already saved",
            "Failure": "GOATS did not save o-1",
        }
        assert response.data["messages"][-1]["message"] == said[expected_status]

    def test_save_observation_only_not_saved_says_why(self, mocker):
        self._mock_validated_serializers(mocker, with_instrument=True)
        mocker.patch.object(
            GPPObservationViewSet,
            "_create_goats_observation",
            side_effect=ValueError("boom"),
        )

        save_view = GPPObservationViewSet.as_view({"post": "save_observation_only"})
        request = self.factory.post(self.observation_save_only_url, {})
        force_authenticate(request, user=self.user_with_login)

        message = save_view(request).data["messages"][-1]

        assert message["label"] == "Failed"
        assert message["message"] == "GOATS did not save o-1"
        assert message["details"] == [{"severity": "error", "text": "boom"}]

    def _mock_validated_serializers(self, mocker, with_instrument=False):
        """Patch serializers used in update/create flows to return valid objects."""
        goats_target = mocker.Mock()
        goats_target.id = 99
        goats_target.name = "test-target"

        context = mocker.patch("goats_tom.api_views.gpp.observations.ContextSerializer")
        context_inst = context.return_value
        context_inst.is_valid.return_value = True
        context_inst.gpp_target_id = "t-1"
        context_inst.gpp_observation_id = "o-1"
        context_inst.gpp_program_id = "p-1"
        context_inst.goats_target = goats_target

        # Creating from an approved configuration uses its own context.
        create_context = mocker.patch(
            "goats_tom.api_views.gpp.observations.CreateContextSerializer"
        )
        create_context_inst = create_context.return_value
        create_context_inst.is_valid.return_value = True
        create_context_inst.gpp_program_id = "p-1"
        create_context_inst.goats_target = goats_target
        create_context_inst.instrument = "GMOS_SOUTH_LONG_SLIT"

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
        workflow_ser.return_value.workflow_state_enum = (
            ObservationWorkflowState.INACTIVE
        )

        return goats_target, target_props, obs_props

    def _mock_update_client(self, mocker):
        """Patch ``GPPClient`` so target, observation and workflow updates succeed."""
        client = mocker.patch(
            "goats_tom.api_views.gpp.observations.GPPClient"
        ).return_value

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
        client.workflow_state.get_by_id = AsyncMock(
            return_value=_workflow_read(ObservationWorkflowState.UNDEFINED)
        )
        client.workflow_state.get_by_id_when_ready = AsyncMock(
            return_value=_observation(ObservationWorkflowState.UNDEFINED)
        )
        return client

    def _mock_create_client(self, mocker):
        """Patch ``GPPClient`` so target, observation and workflow creation succeed."""
        mocker.patch("goats_tom.api_views.gpp.observations.CreateObservationInput")
        client = mocker.patch(
            "goats_tom.api_views.gpp.observations.GPPClient"
        ).return_value

        create_target_result = mocker.Mock()
        create_target_result.model_dump.return_value = {
            "createTarget": {"target": {"id": "t-new"}}
        }
        client.target.create_by_program_id = AsyncMock(
            return_value=create_target_result
        )

        create_obs_result = mocker.Mock()
        create_obs_result.model_dump.return_value = {
            "createObservation": {"observation": {"id": "o-new"}}
        }
        client.observation.create = AsyncMock(return_value=create_obs_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )
        client.workflow_state.get_by_id = AsyncMock(
            return_value=_workflow_read(ObservationWorkflowState.UNDEFINED)
        )
        client.workflow_state.get_by_id_when_ready = AsyncMock(
            return_value=_observation(ObservationWorkflowState.UNDEFINED)
        )
        mocker.patch.object(
            GPPObservationViewSet,
            "_create_goats_observation",
            return_value=Response({"id": 1}, status=status.HTTP_201_CREATED),
        )
        return client

    def test_create_and_save_labels_the_too_activation(self, mocker):
        """A new ToO carries its activation in the title and the observer notes."""
        _, target_props, obs_props = self._mock_validated_serializers(mocker)
        obs_props.observer_notes = "Follow up"
        self._mock_create_client(mocker)

        request = self.factory.post(
            self.observation_create_and_save_url,
            {"finderCharts": "{}", "tooActivationSelect": "RAPID"},
        )
        force_authenticate(request, user=self.user_with_login)

        response = self.create_and_save_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert target_props.name == "RAPID test-target"
        assert obs_props.observer_notes == "RAPID\nFollow up"

    def test_update_only_does_not_label_the_too_activation(self, mocker):
        """Only new observations are labelled; an update leaves them as they are."""
        _, target_props, obs_props = self._mock_validated_serializers(mocker)
        obs_props.observer_notes = "Follow up"
        self._mock_update_client(mocker)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": "{}", "tooActivationSelect": "RAPID"},
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert target_props.name == "test-target"
        assert obs_props.observer_notes == "Follow up"

    def test_update_only_happy_path(self, mocker):
        """Exercise update_only target/observation/workflow updates."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "Success"
        assert response.data["summary"] == "Observation updated"
        assert response.data["data"]["updatedTargetId"] == "t-updated"
        assert response.data["data"]["updatedObservationId"] == "o-updated"
        client.target.update_by_id.assert_called_once()
        client.observation.update_by_id.assert_called_once()
        client.workflow_state.update_by_id_with_retry.assert_called_once()

    def _update_with_state_left_alone(self, mocker, data=None, **checked):
        """Update with the state left as read, GPP answering as given when asked."""
        self._mock_validated_serializers(mocker)
        workflow_ser = mocker.patch(
            "goats_tom.api_views.gpp.observations.WorkflowStateSerializer"
        )
        workflow_ser.return_value.workflow_state_enum = None
        client = self._mock_update_client(mocker)
        client.workflow_state.get_by_id_when_ready = AsyncMock(**checked)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}", **(data or {})}
        )
        force_authenticate(request, user=self.user_with_login)
        response = update_view(request)
        assert workflow_ser.call_args.kwargs["optional"] is True
        client.workflow_state.update_by_id_with_retry.assert_not_called()
        return response, client

    def test_update_only_asks_gpp_for_a_state_left_alone(self, mocker):
        """A state the form did not send is kept, and GPP is asked what it is."""
        response, client = self._update_with_state_left_alone(
            mocker, return_value=_observation(ObservationWorkflowState.DEFINED)
        )

        client.workflow_state.get_by_id_when_ready.assert_called_once()
        assert client.workflow_state.get_by_id_when_ready.call_args.args == ("o-1",)
        assert response.data["status"] == "Success"
        assert response.data["summary"] == "Observation updated"
        assert response.data["messages"][-1] == {
            "stage": "Update Workflow State",
            "status": "Success",
            "message": "Defined",
            "details": [],
            "label": "",
        }

    def test_update_only_saves_even_if_the_state_cannot_be_checked(self, mocker):
        """GPP has the changes, so this is a warning, not a failure."""
        response, _ = self._update_with_state_left_alone(
            mocker, side_effect=GPPClientError("WorkflowStateDomain: Out of time.")
        )

        assert response.data["status"] == "Partial Success"
        assert (
            response.data["summary"]
            == "Observation updated; state could not be confirmed"
        )
        state = response.data["messages"][-1]
        assert state["status"] == "Warning"
        assert state["label"] == "Not checked"
        assert (
            state["message"]
            == "Could not retrieve the observation state of o-1 from GPP"
        )
        assert state["details"] == [{"severity": "error", "text": "Out of time."}]

    def test_update_only_says_the_state_check_timed_out_not_the_update(self, mocker):
        """The changes are saved, so there is nothing to check or try again."""
        response, _ = self._update_with_state_left_alone(
            mocker, side_effect=ReadTimeout("")
        )

        assert (
            response.data["summary"]
            == "Observation updated; state could not be confirmed"
        )
        state = response.data["messages"][-1]
        assert state["label"] == "Not checked"
        assert (
            state["message"]
            == "Could not retrieve the observation state of o-1 from GPP"
        )
        assert state["details"] == [
            {"severity": "error", "text": "GPP did not respond in time."}
        ]

    def test_update_only_says_whose_state_gpp_did_not_say(self, mocker):
        response, _ = self._update_with_state_left_alone(
            mocker, side_effect=_multi_error("Internal error.")
        )

        state = response.data["messages"][-1]
        assert (
            state["message"]
            == "Could not retrieve the observation state of o-1 from GPP"
        )
        assert state["details"] == [{"severity": "error", "text": "Internal error."}]

    def test_update_only_does_not_ask_for_the_state_of_a_calibration(self, mocker):
        """Nothing of it was saved that could change what GPP makes of it."""
        response, client = self._update_with_state_left_alone(
            mocker, {"isCalibration": "true", "hiddenObservationIdInput": "o-1"}
        )

        client.workflow_state.get_by_id_when_ready.assert_not_called()
        assert response.data["status"] == "Success"
        assert response.data["summary"] == "No changes requested"
        assert response.data["messages"][-1]["message"] == "o-1 unchanged"

    def test_update_only_refused_state_gives_gpp_reasons(self, mocker):
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            side_effect=_transition_error(
                [WorkflowReason("ERROR", "CONFIGURATION_ERROR", "Select a band.")]
            )
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.data["summary"] == (
            "Observation updated, but not set to Inactive"
        )
        state = response.data["messages"][-1]
        assert state["label"] == "Undefined"
        assert (
            state["message"]
            == "o-1 is Undefined. GPP could not change its state to Inactive"
        )
        assert state["details"] == [{"severity": "error", "text": "Select a band."}]
        client.workflow_state.get_by_id.assert_called_once_with(observation_id="o-1")

    @pytest.mark.parametrize(
        "form_data, expected_subtitle",
        [
            ({"finderCharts": "{}"}, "GOATS:1.2.3"),
            (
                {"finderCharts": "{}", "discoverySurveyInput": "  Rubin  "},
                "GOATS:1.2.3:Rubin",
            ),
        ],
    )
    def test_update_only_sets_discovery_survey_subtitle(
        self, mocker, form_data, expected_subtitle
    ):
        """The survey submitted by the form is written to the GPP subtitle."""
        _, _, obs_props = self._mock_validated_serializers(mocker)
        mocker.patch(
            "goats_tom.api_views.gpp.observations.get_goats_version",
            return_value="1.2.3",
        )
        self._mock_update_client(mocker)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(self.observation_update_and_save_url, form_data)
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert obs_props.subtitle == expected_subtitle

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
        client.target.get_by_id = AsyncMock(
            return_value=_answer({"target": {"existence": Existence.PRESENT}})
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
        assert response.data["summary"] == "Observation updated; target update failed"
        stages = {m["stage"]: m for m in response.data["messages"]}
        assert stages["Update Sidereal Target"]["status"] == "Error"
        assert stages["Update Sidereal Target"]["message"] == (
            "Your GPP account cannot edit t-1"
        )
        assert stages["Update Observation"]["status"] == "Success"
        # The state is of the observation, which was saved.
        assert stages["Update Workflow State"]["status"] == "Success"

    def _update(self, mocker, **observation_update):
        """Update an observation whose GPP update ends as given, and return the
        messages by stage, the response and the client."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.observation.update_by_id = AsyncMock(**observation_update)
        client.observation.get_by_id = AsyncMock(
            return_value=_answer({"observation": {"existence": Existence.PRESENT}})
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)
        response = update_view(request)
        return {m["stage"]: m for m in response.data["messages"]}, response, client

    def test_update_only_observation_not_editable_skips_workflow_state(self, mocker):
        """GPP leaves out what the account cannot edit, without an error."""
        messages, response, client = self._update(
            mocker, return_value=_answer({"updateObservations": {"observations": []}})
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "Failure"
        assert response.data["summary"] == "Observation not updated"
        observation = messages["Update Observation"]
        assert observation["status"] == "Error"
        assert observation["label"] == "No permission"
        assert observation["message"] == "Your GPP account cannot edit o-1"
        assert observation["details"] == [
            {"severity": "note", "text": NOT_EDITABLE_REASON}
        ]
        assert messages["Update Workflow State"] == {
            "stage": "Update Workflow State",
            "status": "Skipped",
            "message": "Not attempted",
            "details": [],
            "label": "",
        }
        client.workflow_state.update_by_id_with_retry.assert_not_called()

    def test_update_only_lists_each_gpp_error_and_skips_workflow_state(self, mocker):
        """GPP's reasons come one by one, and the state waits for a saved one."""
        messages, response, client = self._update(
            mocker,
            side_effect=_multi_error("A grating is required.", "A fpu is required"),
        )

        assert response.data["status"] == "Failure"
        assert response.data["summary"] == "Observation not updated"
        observation = messages["Update Observation"]
        assert observation["status"] == "Error"
        assert observation["label"] == "Refused"
        assert observation["message"] == "GPP did not accept the changes to o-1"
        assert observation["details"] == [
            {"severity": "error", "text": "A grating is required."},
            {"severity": "error", "text": "A fpu is required"},
        ]
        assert messages["Update Workflow State"]["status"] == "Skipped"
        client.workflow_state.update_by_id_with_retry.assert_not_called()

    def test_update_only_observation_refused_for_its_state_says_so(self, mocker):
        """GPP leaves it out with an error here: the account is not to blame."""
        reason = "Observation o-1 is ineligible due to its workflow state (Ongoing)."
        messages, _, client = self._update(
            mocker,
            side_effect=_multi_error(
                reason, data={"updateObservations": {"observations": []}}
            ),
        )

        assert messages["Update Observation"]["details"] == [
            {"severity": "error", "text": reason}
        ]
        client.observation.get_by_id.assert_not_called()

    def test_update_only_observation_saved_with_errors_is_saved(self, mocker):
        """GPP saves an observation it has no sequence for, and reports it: the
        state is still set."""
        messages, response, client = self._update(
            mocker,
            side_effect=_multi_error(
                "The background calculation has not (yet) produced a value",
                data={"updateObservations": {"observations": [{"id": "o-updated"}]}},
            ),
        )

        assert response.data["status"] == "Success"
        assert response.data["data"]["updatedObservationId"] == "o-updated"
        assert messages["Update Observation"]["status"] == "Success"
        client.workflow_state.update_by_id_with_retry.assert_called_once()

    @pytest.mark.parametrize(
        "update, expected_status, expected_summary",
        [
            (
                {"return_value": _mock_workflow_state_result("INACTIVE")},
                "Success",
                "Calibration state updated to Inactive",
            ),
            (
                {"side_effect": ValueError("boom")},
                "Failure",
                "Calibration state could not be updated",
            ),
        ],
        ids=["set", "not set"],
    )
    def test_update_only_calibration_says_what_happened_to_its_state(
        self, mocker, update, expected_status, expected_summary
    ):
        """GOATS sets only the state of a calibration, so it saves nothing else."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(**update)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {
                "finderCharts": "{}",
                "isCalibration": "true",
                "hiddenObservationIdInput": "o-1",
            },
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.data["status"] == expected_status
        assert response.data["summary"] == expected_summary
        # No other step of a calibration says which one it is.
        assert response.data["messages"][-1]["message"] == (
            "o-1 Inactive"
            if expected_status == "Success"
            else "o-1 is Undefined. GPP could not change its state to Inactive"
        )
        client.observation.update_by_id.assert_not_called()

    def test_update_only_calibration_set_all_the_same_says_which_one_it_is(
        self, mocker
    ):
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            side_effect=ReadTimeout("")
        )
        client.workflow_state.get_by_id = AsyncMock(
            return_value=_workflow_read(ObservationWorkflowState.INACTIVE)
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {
                "finderCharts": "{}",
                "isCalibration": "true",
                "hiddenObservationIdInput": "o-1",
            },
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        assert response.data["status"] == "Success"
        assert response.data["messages"][-1]["message"] == "o-1 Inactive"

    def test_update_only_names_the_observation_whose_form_is_not_valid(self, mocker):
        """Many observations may share a target, so the ID tells which one it is."""
        mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        ).return_value.is_valid.side_effect = ValidationError({"bandSelect": ["No."]})

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": "{}", "hiddenObservationIdInput": "o-1"},
        )
        force_authenticate(request, user=self.user_with_login)

        message = update_view(request).data["messages"][-1]

        assert message["message"] == "Fix these fields of o-1 and try again"
        assert message["details"] == [{"severity": "error", "text": "Band: No."}]

    def test_update_only_says_what_happened_to_each_step(self, mocker):
        self._mock_validated_serializers(mocker)
        self._mock_update_client(mocker)

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        assert [m["message"] for m in update_view(request).data["messages"]] == [
            "Checked",
            "Checked",
            "Checked",
            "t-updated updated",
            "o-updated updated",
            "Inactive",
        ]

    def test_update_only_state_refused_by_gpp_lists_its_errors(self, mocker):
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            side_effect=_multi_error("Not authorized.")
        )

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        message = update_view(request).data["messages"][-1]

        assert message["label"] == "Undefined"
        assert (
            message["message"]
            == "o-1 is Undefined. GPP could not change its state to Inactive"
        )
        assert message["details"] == [{"severity": "error", "text": "Not authorized."}]
        client.workflow_state.get_by_id.assert_called_once_with(observation_id="o-1")

    def test_update_only_target_refused_by_gpp_says_so(self, mocker):
        """Each reason is read away from its step, so it says what it is about."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.target.update_by_id = AsyncMock(side_effect=_multi_error("No name."))

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        messages = {m["stage"]: m for m in update_view(request).data["messages"]}

        target = messages["Update Sidereal Target"]
        assert target["label"] == "Refused"
        assert target["message"] == "GPP did not accept the changes to t-1"

    @pytest.mark.parametrize(
        "kind, stage, expected",
        [
            ("target", "Update Sidereal Target", "t-1"),
            ("observation", "Update Observation", "o-1"),
        ],
    )
    def test_update_only_timeout_says_what_to_check(
        self, mocker, kind, stage, expected
    ):
        """GPP may have saved it all the same, so it is not said to have failed."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        getattr(client, kind).update_by_id = AsyncMock(side_effect=ReadTimeout(""))

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        messages = {m["stage"]: m for m in update_view(request).data["messages"]}

        assert messages[stage]["label"] == "Not confirmed"
        assert messages[stage]["message"] == (
            f"GPP did not respond in time. Check {expected} before trying again."
        )

    @pytest.mark.parametrize(
        "kind, stage, expected",
        [
            ("target", "Update Sidereal Target", "GOATS could not update t-1"),
            ("observation", "Update Observation", "GOATS could not update o-1"),
        ],
    )
    def test_update_only_unexpected_error_says_what_it_is_about(
        self, mocker, kind, stage, expected
    ):
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        getattr(client, kind).update_by_id = AsyncMock(side_effect=ValueError("boom"))

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        messages = {m["stage"]: m for m in update_view(request).data["messages"]}

        assert messages[stage]["label"] == "Failed"
        assert messages[stage]["message"] == expected
        assert messages[stage]["details"] == [{"severity": "error", "text": "boom"}]

    @pytest.mark.parametrize("kind", ["target", "observation"])
    def test_create_and_save_unexpected_error_says_what_it_is_about(self, mocker, kind):
        self._mock_validated_serializers(mocker, with_instrument=True)
        client = self._mock_create_client(mocker)
        error = AsyncMock(side_effect=ValueError("boom"))
        if kind == "target":
            client.target.create_by_program_id = error
        else:
            client.observation.create = error

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        message = self.create_and_save_view(request).data["messages"][-1]

        assert message["label"] == "Failed"
        assert message["message"] == f"GOATS could not create the {kind}"

    def test_create_and_save_names_the_new_observation(self, mocker):
        self._mock_validated_serializers(mocker, with_instrument=True)
        self._mock_create_client(mocker)

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        messages = self.create_and_save_view(request).data["messages"]

        assert [m["message"] for m in messages] == [
            "Checked",
            "Checked",
            "Checked",
            "t-new created",
            "o-new created",
            "Inactive",
            "Saved",
        ]

    @pytest.mark.parametrize("kind", ["target", "observation"])
    def test_create_and_save_timeout_says_what_to_check(self, mocker, kind):
        """Trying again without checking may create it twice."""
        self._mock_validated_serializers(mocker, with_instrument=True)
        client = self._mock_create_client(mocker)
        if kind == "target":
            client.target.create_by_program_id = AsyncMock(side_effect=ReadTimeout(""))
        else:
            client.observation.create = AsyncMock(side_effect=ReadTimeout(""))

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        message = self.create_and_save_view(request).data["messages"][-1]

        assert message["message"] == (
            "GPP did not respond in time. "
            f"Check whether it created the {kind} before trying again."
        )

    def test_create_and_save_state_refused_by_gpp_names_the_observation(self, mocker):
        self._mock_validated_serializers(mocker, with_instrument=True)
        client = self._mock_create_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            side_effect=_multi_error("Select a band.")
        )

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        messages = {
            m["stage"]: m for m in self.create_and_save_view(request).data["messages"]
        }

        state = messages["Update Workflow State"]
        assert state["label"] == "Undefined"
        assert (
            state["message"]
            == "o-new is Undefined. GPP could not change its state to Inactive"
        )
        client.workflow_state.get_by_id.assert_called_once_with(observation_id="o-new")

    def test_create_and_save_not_saved_in_goats_says_why(self, mocker):
        self._mock_validated_serializers(mocker, with_instrument=True)
        self._mock_create_client(mocker)
        mocker.patch.object(
            GPPObservationViewSet,
            "_create_goats_observation",
            side_effect=ValueError("Database is locked."),
        )

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = self.create_and_save_view(request)

        assert response.data["summary"] == (
            "Observation created, but not saved in GOATS"
        )
        message = response.data["messages"][-1]
        assert message["label"] == "Failed"
        assert message["message"] == "GOATS did not save o-new"
        assert message["details"] == [
            {"severity": "error", "text": "Database is locked."}
        ]

    def test_update_only_sends_each_step_as_it_ends(self, mocker):
        """With a progress id, each step reaches the page as it ends, in order."""
        self._mock_validated_serializers(mocker)
        self._mock_update_client(mocker)
        progress = mocker.patch("goats_tom.api_views.gpp.observations.GPPProgress")

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": "{}", "progressId": "p-1"},
        )
        force_authenticate(request, user=self.user_with_login)

        response = update_view(request)

        progress.assert_called_once_with(self.user_with_login.pk, "p-1")
        assert [c.args for c in progress.return_value.send.call_args_list] == [
            (m["stage"], m["status"], m["message"]) for m in response.data["messages"]
        ]

    def test_update_only_sends_what_the_steps_have_room_for(self, mocker):
        """A step that failed says it in a couple of words, not why."""
        self._mock_validated_serializers(mocker)
        client = self._mock_update_client(mocker)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            side_effect=_multi_error("Not authorized.")
        )
        progress = mocker.patch("goats_tom.api_views.gpp.observations.GPPProgress")

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": "{}", "progressId": "p-1"},
        )
        force_authenticate(request, user=self.user_with_login)

        update_view(request)

        assert progress.return_value.send.call_args.args == (
            "Update Workflow State",
            "Error",
            "Undefined",
        )

    def test_update_only_sends_the_step_it_stopped_at(self, mocker):
        mocker.patch(
            "goats_tom.api_views.gpp.observations.ContextSerializer"
        ).return_value.is_valid.side_effect = ValueError("bad data")
        mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        progress = mocker.patch("goats_tom.api_views.gpp.observations.GPPProgress")

        update_view = GPPObservationViewSet.as_view({"post": "update_only"})
        request = self.factory.post(
            self.observation_update_and_save_url,
            {"finderCharts": "{}", "progressId": "p-1"},
        )
        force_authenticate(request, user=self.user_with_login)

        update_view(request)

        assert progress.return_value.send.call_args.args == (
            "Data Validation",
            "Error",
            "Not valid",
        )

    def test_create_and_save_refused_by_gpp_says_so(self, mocker):
        self._mock_validated_serializers(mocker, with_instrument=True)
        client = self._mock_create_client(mocker)
        client.target.create_by_program_id = AsyncMock(
            side_effect=_multi_error("The name is required.")
        )

        request = self.factory.post(
            self.observation_create_and_save_url, {"finderCharts": "{}"}
        )
        force_authenticate(request, user=self.user_with_login)

        response = self.create_and_save_view(request)

        assert response.data["status"] == "Failure"
        assert response.data["summary"] == "Observation not created"
        assert response.data["messages"][-1]["message"] == (
            "GPP did not accept the target"
        )
        assert response.data["messages"][-1]["details"] == [
            {"severity": "error", "text": "The name is required."}
        ]

    def test_create_and_save_happy_path(self, mocker):
        """Exercise the full create_and_save flow with mocked serializers."""
        goats_target, target_props, obs_props = self._mock_validated_serializers(
            mocker, with_instrument=True
        )
        # CloneObservationInput is a pydantic model that rejects Mock objects for
        # `set_`, so stub it out — observation_properties comes from a mocked
        # serializer.
        mocker.patch("goats_tom.api_views.gpp.observations.CreateObservationInput")

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        create_target_result = mocker.Mock()
        create_target_result.model_dump.return_value = {
            "createTarget": {"target": {"id": "t-new"}}
        }
        client.target.create_by_program_id = AsyncMock(
            return_value=create_target_result
        )

        create_obs_result = mocker.Mock()
        create_obs_result.model_dump.return_value = {
            "createObservation": {
                "observation": {
                    "id": "o-new",
                    "reference": {"label": "obs-ref-new"},
                }
            }
        }
        client.observation.create = AsyncMock(return_value=create_obs_result)
        client.workflow_state.update_by_id_with_retry = AsyncMock(
            return_value=_mock_workflow_state_result("INACTIVE")
        )

        # Skip the GOATS save step — it uses the TOM viewset that requires DB state.
        mocker.patch.object(
            GPPObservationViewSet,
            "_create_goats_observation",
            return_value=Response({"id": 1}, status=status.HTTP_201_CREATED),
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
        client.target.create_by_program_id.assert_called_once()
        client.observation.create.assert_called_once()

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

    def test_update_only_processes_finder_charts_when_to_delete_present(self, mocker):
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

    def test_update_only_workflow_state_missing_state_renders_unknown(self, mocker):
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
        assert stages["Update Workflow State"] == "Unknown"

    def test_create_and_save_create_target_returns_no_id(self, mocker):
        """create_and_save fails fast when the created target has no id."""
        self._mock_validated_serializers(mocker, with_instrument=True)

        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        client = mock_client.return_value

        create_target_result = mocker.Mock()
        create_target_result.model_dump.return_value = {"createTarget": {"target": {}}}
        client.target.create_by_program_id = AsyncMock(
            return_value=create_target_result
        )

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
        mock_client.return_value.observation.get_all = AsyncMock(
            return_value=mock_result
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

    def test_list_observations_with_program_id_flags_the_toos(self, mocker):
        too_obs = {
            "id": "o-too",
            "targetEnvironment": {
                "asterism": [
                    {"id": "t-1", "opportunity": {"__typename": "Opportunity"}}
                ]
            },
            "workflow": {"value": {"state": "DEFINED"}},
        }
        normal_obs = {
            "id": "o-norm",
            "targetEnvironment": {"asterism": [{"id": "t-2", "opportunity": None}]},
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
        # Every observation is listed, flagged so the UI can group them by type.
        assert response.data["matches"]["count"] == 2
        assert response.data["matches"]["results"] == [
            {**too_obs, "isToo": True},
            {**normal_obs, "isToo": False},
        ]
        assert response.data["hasMore"] is True
        mock_client.return_value.goats.get_observations_by_program_id.assert_called_once_with(
            program_id="p-1"
        )

    def test_list_observations_includes_unapproved_too(self, mocker):
        unapproved_too_obs = {
            "id": "o-too-unapproved",
            "targetEnvironment": {
                "asterism": [
                    {"id": "t-1", "opportunity": {"__typename": "Opportunity"}}
                ]
            },
            "workflow": {"value": {"state": "UNAPPROVED"}},
        }
        normal_obs = {
            "id": "o-norm",
            "targetEnvironment": {"asterism": [{"id": "t-2", "opportunity": None}]},
        }
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_payload = mocker.Mock()
        mock_payload.model_dump.return_value = {
            "observations": {
                "matches": [unapproved_too_obs, normal_obs],
                "hasMore": False,
            }
        }
        mock_client.return_value.goats.get_observations_by_program_id = AsyncMock(
            return_value=mock_payload
        )

        request = self.factory.get(self.observations_url, {"program_id": "p-1"})
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        # Approval no longer decides what is listed; the ToO select is fed by
        # the approved configuration requests instead.
        assert response.data["matches"]["count"] == 2
        assert response.data["matches"]["results"] == [
            {**unapproved_too_obs, "isToo": True},
            {**normal_obs, "isToo": False},
        ]

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
        mock_client.return_value.observation.get_by_id = AsyncMock(
            return_value=mock_result
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

    def test_normalize_finder_charts_without_payload_returns_empty_structure(self):
        data = {}

        out = self.viewset._normalize_finder_charts(data)

        assert out["finderCharts"] == {
            "toAdd": [],
            "toDelete": [],
            "toUnassign": [],
        }

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

    @staticmethod
    def _mock_program_attachments(mocker, client, attachments):
        """Stub the program attachment listing used to detect existing charts."""
        result = mocker.Mock()
        result.model_dump.return_value = {"program": {"attachments": attachments}}
        client.attachment.get_all_by_program_id = mocker.Mock(return_value=result)
        return result

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(mocker, client, [])

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(mocker, client, [])

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

    @pytest.mark.parametrize("overwrite", [False, True])
    def test_process_finder_charts_same_name_honours_overwrite(
        self, mocker, overwrite
    ):
        """A stored chart of the same name is replaced only when asked to."""
        file1 = SimpleUploadedFile("FC1.png", b"abc", content_type="image/png")

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(
            mocker,
            client,
            [
                {
                    "id": "prog-fc-1",
                    "fileName": "fc1.png",
                    "fileSize": 3,
                    "attachmentType": AttachmentType.FINDER,
                },
                {
                    "id": "prog-other",
                    "fileName": "proposal.pdf",
                    "fileSize": 3,
                    "attachmentType": AttachmentType.SCIENCE,
                },
            ],
        )

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "first", "file": file1, "overwrite": overwrite}
                ],
            },
        )

        client.attachment.upload.assert_not_called()
        assert out == ["prog-fc-1"]

        if overwrite:
            client.attachment.update_by_id.assert_called_once_with(
                attachment_id="prog-fc-1",
                file_name="FC1.png",
                description="first",
                content=b"abc",
            )
        else:
            client.attachment.update_by_id.assert_not_called()

    @pytest.mark.parametrize("overwrite", [False, True])
    def test_process_finder_charts_different_size_reuses_or_overwrites(
        self, mocker, overwrite
    ):
        """A same-name chart of a different size never uploads a duplicate."""
        file1 = SimpleUploadedFile("fc1.png", b"abcdef", content_type="image/png")

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(
            mocker,
            client,
            [
                {
                    "id": "prog-fc-1",
                    "fileName": "fc1.png",
                    "fileSize": 3,
                    "attachmentType": AttachmentType.FINDER,
                }
            ],
        )

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "first", "file": file1, "overwrite": overwrite}
                ],
            },
        )

        client.attachment.upload.assert_not_called()
        assert out == ["prog-fc-1"]

        if overwrite:
            client.attachment.update_by_id.assert_called_once_with(
                attachment_id="prog-fc-1",
                file_name="fc1.png",
                description="first",
                content=b"abcdef",
            )
        else:
            client.attachment.update_by_id.assert_not_called()

    @pytest.mark.parametrize(
        "key, deletes_from_program",
        [("toDelete", True), ("toUnassign", False)],
    )
    def test_process_finder_charts_unassign_keeps_the_program_file(
        self, mocker, key, deletes_from_program
    ):
        """Only ``toDelete`` removes the attachment from the program."""
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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(mocker, client, [])

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={key: ["a1"]},
        )

        # Either way the observation stops referencing it.
        assert out == ["a2"]

        if deletes_from_program:
            client.attachment.delete_by_id.assert_called_once_with(
                attachment_id="a1"
            )
        else:
            client.attachment.delete_by_id.assert_not_called()

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(mocker, client, [])

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
        client.attachment.update_by_id = mocker.Mock()
        self._mock_program_attachments(mocker, client, [])

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


@pytest.mark.parametrize(
    "answer, expected",
    [
        (
            {"return_value": _answer({"target": {"existence": "PRESENT"}})},
            "Your GPP account cannot edit t-1",
        ),
        # No longer visible: the account was taken out of the program.
        (
            {"return_value": _answer({"target": None})},
            "Your GPP account cannot edit t-1",
        ),
        (
            {"return_value": _answer({"target": {"existence": Existence.DELETED}})},
            "t-1 was deleted in GPP",
        ),
        # GPP answers, and reports something else besides.
        (
            {
                "side_effect": _multi_error(
                    "No sequence.", data={"target": {"existence": "DELETED"}}
                )
            },
            "t-1 was deleted in GPP",
        ),
    ],
    ids=["present", "not visible", "deleted", "deleted with errors"],
)
def test_left_out_error_tells_deleted_from_not_editable(answer, expected):
    error = left_out_error(AsyncMock(**answer), "target", "t-1")

    message = stage_error(Stage.UPDATE_TARGET, error)
    assert message.message == expected
    deleted = expected.endswith("deleted in GPP")
    assert message.label == ("Deleted" if deleted else "No permission")


@pytest.mark.parametrize(
    "existence, expected",
    [
        (Existence.PRESENT, "Your GPP account cannot edit o-1"),
        (Existence.DELETED, "o-1 was deleted in GPP"),
    ],
)
def test_left_out_error_names_the_observation(existence, expected):
    """Many observations may share a target, so the ID tells which one it is."""
    answer = _answer({"observation": {"existence": existence}})

    error = left_out_error(AsyncMock(return_value=answer), "observation", "o-1")

    assert str(error) == expected


def test_left_out_error_does_not_guess_without_an_answer():
    """GPP did not answer, so why it left the item out is not known."""
    with pytest.raises(GraphQLClientGraphQLMultiError):
        left_out_error(
            AsyncMock(side_effect=_multi_error("Internal error.")), "target", "t-1"
        )


def test_build_failure_response_lists_form_errors_by_field():
    """A form error names each field for people, instead of DRF's nested repr."""
    error = ValidationError(
        {
            "hiddenObservingModeInput": [CANNOT_EDIT_IFU],
            "timingWindows": [{}, {"end": {"non_field_errors": [END_REQUIRED]}}],
            "non_field_errors": ["The form is incomplete."],
        }
    )

    message = build_failure_response(Stage.VALIDATION, error, []).data["messages"][-1]

    reasons = [
        f"Observing mode: {CANNOT_EDIT_IFU}",
        "Timing windows › #2 › End: Specify an end time or a duration.",
        "The form is incomplete.",
    ]
    assert message["message"] == "Fix these fields and try again"
    assert message["details"] == [{"severity": "error", "text": r} for r in reasons]


@pytest.mark.parametrize(
    "error, logs_traceback",
    [
        (KeyError("asterism"), True),
        (ValidationError({"bandSelect": ["Required."]}), False),
        ("GPP login credentials are not configured for this user.", False),
    ],
    ids=["unexpected", "form", "text"],
)
def test_build_failure_response_logs_where_an_unexpected_error_came_from(
    caplog, error, logs_traceback
):
    with caplog.at_level(logging.ERROR, logger="goats_tom.api_views.gpp.observations"):
        build_failure_response(Stage.VALIDATION, error, [])

    assert bool(caplog.records[-1].exc_info) is logs_traceback


@pytest.mark.parametrize(
    "stage, expected",
    [
        (Stage.CREDENTIALS_CHECK, "Observation not sent to GPP"),
        (Stage.NORMALIZATION, "Observation not sent to GPP"),
        (Stage.VALIDATION, "Observation not sent to GPP"),
        (Stage.UPDATE_OBSERVATION, "Observation not updated"),
        (Stage.CREATE_TARGET, "Observation not created"),
        (Stage.CREATE_OBSERVATION, "Observation not created"),
    ],
)
def test_failure_summary(stage, expected):
    assert failure_summary(stage) == expected


DEFINED = ObservationWorkflowState.DEFINED


def _messages(*failed: Stage) -> list[StageMessage]:
    """The messages of a request whose `failed` stages did not go through."""
    return [
        StageMessage(
            stage=stage,
            status=MessageStatus.ERROR if stage in failed else MessageStatus.SUCCESS,
            message="",
        )
        for stage in Stage
    ]


@pytest.mark.parametrize(
    "failed, expected",
    [
        ([], "Observation updated"),
        ([Stage.UPDATE_WORKFLOW_STATE], "Observation updated, but not set to Defined"),
        ([Stage.UPDATE_TARGET], "Observation updated; target update failed"),
        (
            [Stage.GOATS_OBSERVATION_SAVE],
            "Observation updated, but not saved in GOATS",
        ),
        (
            [Stage.UPDATE_TARGET, Stage.UPDATE_WORKFLOW_STATE],
            "Observation updated, with problems",
        ),
    ],
)
def test_summarize(failed, expected):
    assert summarize(_messages(*failed), "Observation updated", DEFINED) == expected


@pytest.mark.parametrize(
    "state, failed, expected",
    [
        (None, [], "No changes requested"),
        (DEFINED, [], "Calibration state updated to Defined"),
        (
            DEFINED,
            [Stage.UPDATE_WORKFLOW_STATE],
            "Calibration state could not be updated",
        ),
    ],
)
def test_summarize_calibration(state, failed, expected):
    assert summarize_calibration(_messages(*failed), state) == expected


CONDITIONS = ObservationValidationCode.CONDITIONS_UNLIKELY
CONFIGURATION = ObservationValidationCode.CONFIGURATION_ERROR
CFP = ObservationValidationCode.CFP_WARNING
ERROR = ObservationValidationCodeSeverity.ERROR
WARNING = ObservationValidationCodeSeverity.WARNING


def test_workflow_report_gives_the_reasons_errors_first():
    """GPP's reasons, word for word, but not a warning its program dismissed."""
    message = workflow_report(
        _observation(
            ObservationWorkflowState.UNDEFINED,
            errors=[
                (CONDITIONS, WARNING, "Conditions likelihood is 9%."),
                (CONFIGURATION, ERROR, "Select a band.", "Select a grating"),
                (CFP, WARNING, "Base coordinates out of limits."),
            ],
            dismissed=[CFP],
        )
    )

    assert message.status == MessageStatus.WARNING
    assert message.label == "Undefined"
    assert message.message == "o-1 is Undefined"
    assert message.details == [
        {"severity": "error", "text": "Select a band."},
        {"severity": "error", "text": "Select a grating"},
        {"severity": "warning", "text": "Conditions likelihood is 9%."},
    ]


@pytest.mark.parametrize(
    "state, errors, dismissed, expected_status, expected_message",
    [
        ("DEFINED", [], [], "Success", "Defined"),
        (
            "DEFINED",
            [(CONDITIONS, WARNING, "9%.")],
            [],
            "Warning",
            "o-1 is Defined. These warnings keep it from Ready",
        ),
        (
            "DEFINED",
            [(CONDITIONS, WARNING, "9%.")],
            [CONDITIONS],
            "Success",
            "Defined",
        ),
        (
            "UNAPPROVED",
            [(CONFIGURATION, ERROR, "Not requested.")],
            [],
            "Warning",
            "o-1 is Unapproved",
        ),
        # Dismissing is for warnings: an error still counts.
        (
            "UNDEFINED",
            [(CONFIGURATION, ERROR, "Select a band.")],
            [CONFIGURATION],
            "Warning",
            "o-1 is Undefined",
        ),
        # A state the user set is not what the validation makes of it.
        (
            "INACTIVE",
            [(CONFIGURATION, ERROR, "Select a band.")],
            [],
            "Success",
            "Inactive",
        ),
    ],
)
def test_workflow_report_warns_only_of_what_needs_attention(
    state, errors, dismissed, expected_status, expected_message
):
    message = workflow_report(
        _observation(ObservationWorkflowState(state), errors, dismissed)
    )

    assert message.status.value == expected_status
    assert message.message == expected_message
    # A state with nothing to say about it goes in the steps as it is.
    assert message.label == (state.capitalize() if message.details else "")


def test_workflow_report_names_an_error_without_a_text():
    message = workflow_report(
        _observation(ObservationWorkflowState.UNDEFINED, [(CONFIGURATION, ERROR)])
    )

    assert message.details == [{"severity": "error", "text": "CONFIGURATION_ERROR"}]


@pytest.mark.parametrize(
    "error, expected_message, expected_details",
    [
        (
            _transition_error(
                [
                    WorkflowReason("ERROR", "X", "Unapproved."),
                    WorkflowReason("WARNING", "Y", "Overlap."),
                ]
            ),
            "GPP did not set o-1 to Inactive",
            [("error", "Unapproved."), ("warning", "Overlap.")],
        ),
        (
            _transition_error([], allowed=["READY", "DEFINED"]),
            "GPP did not set o-1 to Inactive",
            [("error", "GPP allows Ready, Defined.")],
        ),
        (
            _transition_error([], allowed=[]),
            "GPP did not set o-1 to Inactive",
            [("error", "GPP allows no other state.")],
        ),
        (
            GPPClientError("WorkflowStateDomain: WorkflowStateDomain: Too many tries."),
            "Too many tries.",
            [],
        ),
    ],
    ids=["reasons", "allowed states", "no state allowed", "domain name"],
)
def test_stage_error_of_a_workflow_state(error, expected_message, expected_details):
    message = stage_error(
        Stage.UPDATE_WORKFLOW_STATE,
        error,
        lead="GPP did not set o-1 to Inactive",
        label="Not set to Inactive",
    )

    assert message.label == "Not set to Inactive"
    assert message.message == expected_message
    assert message.details == [
        {"severity": severity, "text": text} for severity, text in expected_details
    ]


@pytest.mark.parametrize(
    "stage, expected",
    [
        (Stage.CREDENTIALS_CHECK, "Not configured"),
        (Stage.NORMALIZATION, "Not valid"),
        (Stage.VALIDATION, "Not valid"),
        (Stage.UPDATE_OBSERVATION, "Failed"),
    ],
)
def test_stage_error_says_it_in_a_couple_of_words(stage, expected):
    """Whatever failed, the steps have no room for a whole sentence."""
    assert stage_error(stage, ValueError("A whole sentence.")).label == expected


@pytest.mark.parametrize(
    "error, expected",
    [
        (_multi_error("No."), "Refused"),
        (_transition_error([]), "Refused"),
        (LeftOutError("o-1 was deleted in GPP", label="Deleted"), "Deleted"),
        (ReadTimeout(""), "Not confirmed"),
        (ValueError("boom"), "Failed"),
    ],
    ids=["refused", "state", "left out", "timeout", "unexpected"],
)
def test_stage_error_says_why_in_the_steps(error, expected):
    """The title already says that it was not updated."""
    assert stage_error(Stage.UPDATE_OBSERVATION, error).label == expected


def test_stage_error_says_what_an_unexpected_error_is_about():
    error = ValueError("ObservationDomain: boom")

    message = stage_error(
        Stage.UPDATE_OBSERVATION, error, failed="GOATS could not update o-1"
    )

    assert message.message == "GOATS could not update o-1"
    assert message.details == [{"severity": "error", "text": "boom"}]


@pytest.mark.parametrize(
    "error", [TimeoutError(), pytest.param(ReadTimeout(""), id="read-timeout")]
)
def test_timeout_message_does_not_claim_the_operation_failed(error):
    message = stage_error(Stage.UPDATE_OBSERVATION, error, check="o-1")
    assert message.label == "Not confirmed"
    assert message.message == (
        "GPP did not respond in time. Check o-1 before trying again."
    )


def test_timeout_message_without_anything_to_check():
    message = stage_error(Stage.UPDATE_OBSERVATION, ReadTimeout(""))
    assert message.message == "GPP did not respond in time."


def _state_error(error, asked=ObservationWorkflowState.READY, **answer):
    """What is said of a state GPP did not set, given its answer on the one it has."""
    client = Mock()
    client.workflow_state.get_by_id = AsyncMock(**answer)
    return state_error(client, error, "o-1", asked)


UNDEFINED_READ = _workflow_read(ObservationWorkflowState.UNDEFINED)


def test_state_error_says_the_state_gpp_has():
    message = _state_error(_multi_error("Select a band."), return_value=UNDEFINED_READ)

    assert message.status == MessageStatus.ERROR
    assert message.label == "Undefined"
    assert (
        message.message == "o-1 is Undefined. GPP could not change its state to Ready"
    )
    assert message.details == [{"severity": "error", "text": "Select a band."}]


@pytest.mark.parametrize(
    "answer",
    [
        {"side_effect": GPPClientError("Out of time.")},
        {
            "return_value": _workflow_read(
                ObservationWorkflowState.UNDEFINED, CalculationState.CALCULATING
            )
        },
    ],
    ids=["no answer", "still calculating"],
)
def test_state_error_does_not_guess_the_state(answer):
    """A state GPP is still calculating may not be the one it ends up with."""
    message = _state_error(_multi_error("Select a band."), **answer)

    assert message.status == MessageStatus.ERROR
    assert message.label == "Not set to Ready"
    assert message.message == "GPP did not set o-1 to Ready"
    assert message.details == [{"severity": "error", "text": "Select a band."}]


def test_state_error_gives_an_unexpected_error_as_the_reason():
    """An error on its own would not say which observation has which state."""
    message = _state_error(
        GPPClientError("WorkflowStateDomain: WorkflowStateDomain: Too many tries."),
        return_value=UNDEFINED_READ,
    )

    assert (
        message.message == "o-1 is Undefined. GPP could not change its state to Ready"
    )
    assert message.details == [{"severity": "error", "text": "Too many tries."}]


def test_state_error_of_a_state_that_was_set_all_the_same():
    """GPP set it and its answer was lost, so nothing went wrong."""
    message = _state_error(
        TimeoutError(), return_value=_workflow_read(ObservationWorkflowState.READY)
    )

    assert message.status == MessageStatus.SUCCESS
    assert message.message == "Ready"
    assert (message.label, message.details) == ("", [])


def test_state_error_of_a_timeout_says_the_state_gpp_has():
    """GOATS just asked, so there is nothing left to confirm."""
    message = _state_error(ReadTimeout(""), return_value=UNDEFINED_READ)

    assert message.label == "Undefined"
    assert (
        message.message == "o-1 is Undefined. GPP could not change its state to Ready"
    )
    assert message.details == [
        {"severity": "error", "text": "GPP did not respond in time."}
    ]


def test_state_error_of_a_timeout_without_an_answer_is_not_confirmed():
    message = _state_error(ReadTimeout(""), side_effect=ReadTimeout(""))

    assert message.label == "Not confirmed"
    assert message.message == "GPP did not confirm the change of o-1 to Ready"
    assert message.details == [
        {
            "severity": "error",
            "text": "GPP did not respond in time. Check o-1 before trying again.",
        }
    ]


def test_summarize_a_result_that_could_not_be_confirmed():
    messages = [stage_error(Stage.UPDATE_TARGET, ReadTimeout(""))]

    assert (
        summarize(messages, "Observation updated", None)
        == "Observation updated; some results could not be confirmed"
    )


def test_summarize_calibration_that_could_not_be_confirmed():
    messages = [stage_error(Stage.UPDATE_WORKFLOW_STATE, ReadTimeout(""))]

    assert (
        summarize_calibration(messages, DEFINED)
        == "Calibration state could not be confirmed"
    )


@pytest.mark.parametrize(
    "stage, expected",
    [
        (Stage.CREATE_TARGET, "Observation not created"),
        (Stage.CREATE_OBSERVATION, "Observation creation could not be confirmed"),
    ],
)
def test_build_failure_response_of_a_timeout(stage, expected):
    """Without its target, the observation was not created for sure."""
    response = build_failure_response(stage, ReadTimeout(""), [], check="it")

    assert response.data["summary"] == expected
    assert response.data["messages"][-1]["message"] == (
        "GPP did not respond in time. Check it before trying again."
    )
