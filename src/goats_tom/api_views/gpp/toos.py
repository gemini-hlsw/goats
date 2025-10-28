"""Handles creating ToOs with GPP."""

__all__ = ["GPPTooViewSet"]

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.enums import ObservationWorkflowState
from gpp_client.api.input_types import TargetEnvironmentInput
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.viewsets import GenericViewSet, mixins
from tom_observations.api_views import ObservationRecordViewSet

from goats_tom.context_processors.goats_version_processor import get_goats_version
from goats_tom.serializers.gpp import (
    CreateTooSerializer,
    ObservationSerializer,
    TargetSerializer,
    WorkflowStateSerializer,
)


class Stage(str, Enum):
    """Stages in the ToO creation process."""

    CREDENTIALS_CHECK = "credentials_check"
    NORMALIZATION = "normalization"
    VALIDATION = "validation"
    CREATE_TARGET = "create_target"
    CREATE_OBSERVATION = "create_observation"
    UPDATE_WORKFLOW_STATE = "update_workflow_state"
    GOATS_OBSERVATION_SAVE = "goats_observation_save"


class MessageStatus(str, Enum):
    """Status of a message in the ToO creation process."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class ResponseStatus(str, Enum):
    """Overall status of the ToO creation response."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


@dataclass
class StageMessage:
    """Message for a specific stage in the ToO creation process."""

    stage: Stage
    status: MessageStatus
    message: str


def build_failure_response(
    stage: Stage,
    error: Exception | str,
    previous_messages: list[StageMessage],
    data: dict[str, Any] | None = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    overall_status: ResponseStatus = ResponseStatus.FAILURE,
) -> Response:
    """Build a structured failure response and append an error message.

    Parameters
    ----------
    stage : Stage
        The stage at which the failure occurred.
    error : Exception | str
        The error that occurred.
    previous_messages : list[StageMessage]
        The list of messages from previous stages.
    data : dict[str, Any] | None = None
        Additional data to include in the response.
    http_status : int = status.HTTP_400_BAD_REQUEST
        The HTTP status code for the response.
    overall_status : ResponseStatus = ResponseStatus.FAILURE
        The overall status of the response.

    Returns
    -------
    Response
        The response containing the failure details.
    """
    print(f"Building failure response for stage: {stage}: {error}")
    error_message = str(error)
    messages = previous_messages + [
        StageMessage(stage=stage, status=MessageStatus.ERROR, message=error_message)
    ]

    return Response(
        {
            "status": overall_status,
            "messages": [asdict(msg) for msg in messages],
            "data": data or {},
        },
        status=http_status,
    )


class GPPTooViewSet(GenericViewSet, mixins.CreateModelMixin):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def _normalize(self, value: str | None) -> str | None:
        """
        Convert empty strings or whitespace to ``None``.

        Parameters
        ----------
        value : str | None
            The input string to normalize.

        Returns
        -------
        str | None
            The normalized string or ``None`` if the input was empty or whitespace.
        """
        return value.strip() if value and value.strip() != "" else None

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Create a ToO target, observation, and sets the workflow in GPP.

        The steps taken to create a ToO observation are:
        1. Clone the target with new properties, setting the target as sidereal.
        2. Clone the observation with new properties, linking to the new target.
        3. Set the workflow state for the new observation.

        Parameters
        ----------
        request : Request
            The request object containing the data for the new target and observation.

        Returns
        -------
        Response
            A DRF Response object containing the details of the created observation.
        """
        messages: list[StageMessage] = []
        data: dict[str, Any] = {}
        status_code = status.HTTP_201_CREATED

        # Ensure the user has GPP credentials.
        if not hasattr(request.user, "gpplogin"):
            return build_failure_response(
                stage=Stage.CREDENTIALS_CHECK,
                error="GPP login credentials are not configured for this user.",
                previous_messages=messages,
            )

        print("Getting GPP credentials for user:", request.user.username)
        credentials = request.user.gpplogin

        messages.append(
            StageMessage(
                stage=Stage.CREDENTIALS_CHECK,
                status=MessageStatus.SUCCESS,
                message="GPP credentials verified.",
            )
        )

        try:
            print("Normalizing request data...")
            normalized_data = {
                key: self._normalize(value) for key, value in request.data.items()
            }
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION, error=e, previous_messages=messages
            )

        try:
            # Setup client to communicate with GPP.
            print("Setting up GPP client...")
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)

            # Validate and extract required IDs for ToO creation.
            create_too_serializer = CreateTooSerializer(data=normalized_data)
            create_too_serializer.is_valid(raise_exception=True)
            gpp_target_id = create_too_serializer.gpp_target_id
            gpp_observation_id = create_too_serializer.gpp_observation_id
            goats_target = create_too_serializer.goats_target
            instrument = create_too_serializer.instrument
            print(
                "Required IDs for ToO creation: ",
                gpp_target_id,
                gpp_observation_id,
                goats_target.id,
                goats_target.name,
                instrument,
            )

            # Serialize and validate target.
            target_serializer = TargetSerializer(data=normalized_data)
            target_serializer.is_valid(raise_exception=True)
            target_properties = target_serializer.to_pydantic()
            target_properties.name = goats_target.name

            # Serialize and validate observation.
            observation_serializer = ObservationSerializer(data=normalized_data)
            observation_serializer.is_valid(raise_exception=True)
            observation_properties = observation_serializer.to_pydantic()

            # Set subtitle to a GOATS identifier for easier tracking.
            try:
                subtitle = f"GOATS:{get_goats_version()}"
            except Exception:
                subtitle = "GOATS"
            observation_properties.subtitle = subtitle

            # Serialize and validate workflow state.
            workflow_state_serializer = WorkflowStateSerializer(data=normalized_data)
            workflow_state_serializer.is_valid(raise_exception=True)
            workflow_state = workflow_state_serializer.workflow_state_enum

            messages.append(
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message="All serializers validated successfully.",
                )
            )

        except Exception as e:
            return build_failure_response(Stage.VALIDATION, e, messages)

        # Create target
        try:
            print("Cloning target...")
            clone_target_result = async_to_sync(client.target.clone)(
                target_id=gpp_target_id, properties=target_properties
            )
            new_target_id = clone_target_result.get("newTarget", {}).get("id")
            print("New target ID:", new_target_id)

            if new_target_id is None:
                raise ValueError("Failed to retrieve new target ID from clone result.")

            data["newTargetId"] = new_target_id
            messages.append(
                StageMessage(
                    stage=Stage.CREATE_TARGET,
                    status=MessageStatus.SUCCESS,
                    message=f"Target created successfully as {new_target_id}.",
                )
            )

        except Exception as e:
            return build_failure_response(Stage.CREATE_TARGET, e, messages)

        # Create observation
        try:
            print("Updating observation properties with new target ID...")
            observation_properties.target_environment = TargetEnvironmentInput(
                asterism=[new_target_id]
            )

            print("Cloning observation...")
            clone_observation_result = async_to_sync(client.observation.clone)(
                observation_id=gpp_observation_id, properties=observation_properties
            )
            new_observation = clone_observation_result.get("newObservation", {})
            new_observation_id = new_observation.get("id")
            print("New observation ID:", new_observation_id)

            if new_observation_id is None:
                raise ValueError(
                    "Failed to retrieve new observation ID from clone result."
                )

            data["newObservationId"] = new_observation_id
            messages.append(
                StageMessage(
                    stage=Stage.CREATE_OBSERVATION,
                    status=MessageStatus.SUCCESS,
                    message=(
                        f"Observation created successfully as {new_observation_id}."
                    ),
                )
            )

        except Exception as e:
            return build_failure_response(Stage.CREATE_OBSERVATION, e, messages)

        # Set workflow state.
        # TODO: Make this smarter.
        try:
            print("Setting workflow state for new observation...")
            self._set_workflow_state_with_retry(
                client=client,
                observation_id=new_observation_id,
                workflow_state=workflow_state,
            )
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SUCCESS,
                    message=f"Workflow state set to {workflow_state.value}.",
                )
            )

        except Exception as e:
            print(f"Failed to set workflow state: {str(e)}")
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.ERROR,
                    message=f"Failed to set workflow state: {str(e)}",
                )
            )

        # Save the created ToO observation to GOATS database.
        try:
            print("Saving ToO observation to GOATS database...")
            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                new_observation=new_observation,
            )

            if tom_response.status_code != status.HTTP_201_CREATED:
                raise ValueError(tom_response.data)

            data["goatsObservation"] = tom_response.data
            messages.append(
                StageMessage(
                    stage=Stage.GOATS_OBSERVATION_SAVE,
                    status=MessageStatus.SUCCESS,
                    message="Observation saved to GOATS database successfully.",
                )
            )

        except Exception as e:
            messages.append(
                StageMessage(
                    stage=Stage.GOATS_OBSERVATION_SAVE,
                    status=MessageStatus.ERROR,
                    message=f"Failed to save observation to GOATS database: {str(e)}",
                )
            )

        # Determine final overall status and HTTP code.
        all_success = all(msg.status == MessageStatus.SUCCESS for msg in messages)

        final_status = (
            ResponseStatus.SUCCESS if all_success else ResponseStatus.PARTIAL_SUCCESS
        )

        if not all_success:
            status_code = status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "status": final_status.value,
                "messages": [asdict(msg) for msg in messages],
                "data": data,
            },
            status=status_code,
        )

    def _set_workflow_state_with_retry(
        self,
        client: GPPClient,
        observation_id: str,
        workflow_state: ObservationWorkflowState,
        *,
        max_attempts: int = 10,
        initial_delay: float = 5.0,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Attempt to set the workflow state, retrying if the observation is not ready.

        There is an initial delay before starting attempts, followed by retries with a
        delay. The initial delay is required as the workflow state won't be ready to be
        set immediately after cloning.

        Parameters
        ----------
        client : GPPClient
            The GPP client instance.
        observation_id : str
            The ID of the observation whose workflow state should be updated.
        workflow_state : ObservationWorkflowState
            The desired workflow state.
        max_attempts : int, default=55
            Maximum number of retry attempts.
        initial_delay : float, default=5.0
            Initial delay in seconds before first attempt.
        retry_delay : float, default=1.0
            Delay in seconds between retry attempts.

        Raises
        ------
        RuntimeError
            If the workflow state could not be set after all retry attempts.
        Exception
            If a non-retryable error occurs.
        """
        # Initial delay before starting attempts since we know the observation won't be
        # ready immediately.
        print(f"Waiting for {initial_delay} seconds before setting workflow state...")
        time.sleep(initial_delay)

        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Attempt {attempt}: Trying to set workflow state...")
                result = async_to_sync(client.workflow_state.update_by_id)(
                    observation_id=observation_id,
                    workflow_state=workflow_state,
                )
                print("Successfully set workflow state:", result)
                return
            except ValueError as e:
                print(f"Attempt {attempt} failed (retryable): {e}")
                time.sleep(retry_delay)
            except Exception as e:
                print(f"Non-retryable error setting workflow state: {e}")
                raise

        raise RuntimeError("Failed to set workflow state after multiple retries.")

    def _create_goats_observation(
        self,
        request: Request,
        target_id: int,
        instrument: str,
        new_observation: dict[str, Any],
        facility: str = "GEM",
    ) -> Response:
        """
        Save the created ToO GPP observation to the GOATS database using the TOM API
        view.

        Parameters
        ----------
        request : Request
            The DRF request object.
        target_id : int
            The ID of the GOATS target to associate with the observation.
        instrument : str
            The observation type (e.g., "GMOS_SOUTH_LONG_SLIT").
        new_observation : dict[str, Any]
            The observation data returned from GPP.
        facility : str, default="GEM"
            The facility name.

        Returns
        -------
        Response
            The DRF response from the TOM ObservationRecordViewSet.
        """
        # Inject required fields into observation parameters.
        new_observation.update(
            {
                "target_id": target_id,
                "facility": facility,
            }
        )

        payload = {
            "target_id": target_id,
            "facility": facility,
            "observation_type": instrument,
            "observing_parameters": new_observation,
        }

        # Use APIRequestFactory to build an internal POST request.
        factory = APIRequestFactory()
        internal_request = factory.post("/api/observations/", payload, format="json")
        internal_request.user = request.user

        # Dispatch request to TOM view.
        view = ObservationRecordViewSet.as_view({"post": "create"})
        return view(internal_request)
