"""Handles grabbing observations and observation details from GPP."""

__all__ = ["GPPObservationViewSet"]

import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, List

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient, GPPDirector
from gpp_client.api.enums import ObservationWorkflowState
from gpp_client.api.input_types import TargetEnvironmentInput
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.viewsets import GenericViewSet, mixins
from tom_observations.api_views import ObservationRecordViewSet

from goats_tom.context_processors.goats_version_processor import get_goats_version
from goats_tom.serializers.gpp import (
    ContextSerializer,
    ObservationSerializer,
    TargetSerializer,
    WorkflowStateSerializer,
)

logger = logging.getLogger(__name__)


class Stage(str, Enum):
    """Stages in the observation creation process."""

    CREDENTIALS_CHECK = "Credentials Check"
    NORMALIZATION = "Data Normalization"
    VALIDATION = "Data Validation"
    CREATE_TARGET = "Create Sidereal Target"
    CREATE_OBSERVATION = "Create Observation"
    UPDATE_WORKFLOW_STATE = "Update Workflow State"
    GOATS_OBSERVATION_SAVE = "Save Observation in GOATS"


class MessageStatus(str, Enum):
    """Status of a message in the observation creation process."""

    SUCCESS = "Success"
    ERROR = "Error"
    WARNING = "Warning"


class ResponseStatus(str, Enum):
    """Overall status of the observation creation response."""

    SUCCESS = "Success"
    PARTIAL_SUCCESS = "Partial Success"
    FAILURE = "Failure"


@dataclass
class StageMessage:
    """Message for a specific stage in the observation creation process."""

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
    logger.error("Error at stage %s: %s", stage.value, error)
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


class GPPObservationViewSet(GenericViewSet, mixins.ListModelMixin):
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

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return a list of GPP observations associated with the authenticated user.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing a list of GPP observations.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        """
        if not hasattr(request.user, "gpplogin"):
            logger.error(
                "GPP login credentials are not configured for user: %s",
                request.user,
            )
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        credentials = request.user.gpplogin
        program_id = request.query_params.get("program_id")

        try:
            # Setup client to communicate with GPP.
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            director = GPPDirector(client)
            if program_id is not None:
                logger.debug(
                    "Retrieving GPP observations for program ID: %s", program_id
                )
                payload = async_to_sync(director.goats.observation.get_all)(
                    program_id=program_id
                )
                # Filter the observations into too and normal categories.
                matches = payload.get("matches", [])
                too_obs = [o for o in matches if self.is_too(o)]
                normal_obs = [o for o in matches if not self.is_too(o)]

                # Build the custom payload response.
                return Response(
                    {
                        "matches": {
                            "too": {"count": len(too_obs), "results": too_obs},
                            "normal": {"count": len(normal_obs), "results": normal_obs},
                        },
                        "hasMore": payload.get("hasMore", False),
                    }
                )
            else:
                logger.debug(
                    "Retrieving all GPP observations for user: %s", request.user
                )
                payload = async_to_sync(client.observation.get_all)()
                return Response(payload)
        except Exception as e:
            logger.exception("Error retrieving GPP observations")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # FIXME: Should I be getting "opportunity" from "firstScienceTarget" instead of the
    # list of asterisms?
    def is_too(self, obs: dict) -> bool:
        """Return whether the observation is a Target of Opportunity (ToO).

        Parameters
        ----------
        obs : dict
            The observation payload returned from GPP. This may or may not
            contain the ``targetEnvironment`` and ``asterism`` keys.

        Returns
        -------
        bool
            ``True`` if the observation is a ToO (opportunity present), ``False``
            otherwise.
        """
        # Need to handle case where any of this data could be missing.
        # This fails silently and returns False if anything is missing.
        target_env = obs.get("targetEnvironment") or {}
        asterisms = target_env.get("asterism") or []
        if not asterisms:
            return False
        return bool(asterisms[0].get("opportunity"))

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Return details for a specific GPP observation by observation ID.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing the details of the requested observation.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        KeyError
            If 'pk' (the observation ID) is not present in kwargs.
        """
        # This is not in-use for right now but keeping it as a placeholder.
        observation_id = kwargs["pk"]

        if not hasattr(request.user, "gpplogin"):
            logger.error(
                "GPP login credentials are not configured for user: %s",
                request.user,
            )
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)
            observation = async_to_sync(client.observation.get_by_id)(
                observation_id=observation_id
            )
            return Response(observation)
        except Exception as e:
            logger.exception("Error retrieving GPP observation")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="save-only")
    def save_observation_only(self, request: Request, *args, **kwargs) -> Response:
        """Save an existing GPP observation to the GOATS database without creating a
        new one in GPP.

        Parameters
        ----------
        request : Request
            The request object containing the data for the observation to save.

        Returns
        -------
        Response
            A DRF Response object containing the details of the saved observation.
        """
        messages: list[StageMessage] = []
        data: dict[str, Any] = {}
        logger.info("Saving GPP observation to GOATS database")
        try:
            normalized_data = {
                key: self._normalize(value) for key, value in request.data.items()
            }
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION, error=e, previous_messages=messages
            )
        messages.append(
            StageMessage(
                stage=Stage.NORMALIZATION,
                status=MessageStatus.SUCCESS,
                message="Form data normalized successfully.",
            )
        )

        logger.debug("Serializing context for GPP observation save")
        try:
            # Validate and extract required IDs for observation creation.
            context_serializer = ContextSerializer(data=normalized_data)
            context_serializer.is_valid(raise_exception=True)
            goats_target = context_serializer.goats_target
            instrument = context_serializer.instrument
            formatted_observation = context_serializer.format_observation()

            messages.append(
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message="All serializers validated successfully.",
                )
            )

        except Exception as e:
            return build_failure_response(Stage.VALIDATION, e, messages)

        # Save the existing observation to GOATS database.
        logger.debug("Creating GOATS observation record")
        try:
            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                observation=formatted_observation,
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

        return self._build_structured_response(messages=messages, data=data)

    @action(detail=False, methods=["post"], url_path="update-and-save")
    def update_and_save_observation(
        self, request: Request, *args, **kwargs
    ) -> Response:
        """Update an existing GPP observation and save it to the GOATS database.

        Parameters
        ----------
        request : Request
            The request object containing the data for the observation to update and
            save.

        Returns
        -------
        Response
            A DRF Response object containing the details of the updated and saved
            observation.
        """
        return Response(
            {"detail": "Update and save observation functionality is not implemented."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    @action(detail=False, methods=["post"], url_path="create-and-save")
    def create_and_save_observation(
        self, request: Request, *args, **kwargs
    ) -> Response:
        """Create a sidereal target, observation, and sets the workflow in GPP.

        The steps taken to create a observation are:
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

        logger.info(
            "Creating observation on GPP and saving observation to GOATS database"
        )

        # Ensure the user has GPP credentials.
        if not hasattr(request.user, "gpplogin"):
            return build_failure_response(
                stage=Stage.CREDENTIALS_CHECK,
                error="GPP login credentials are not configured for this user.",
                previous_messages=messages,
            )
        credentials = request.user.gpplogin

        messages.append(
            StageMessage(
                stage=Stage.CREDENTIALS_CHECK,
                status=MessageStatus.SUCCESS,
                message="GPP credentials verified.",
            )
        )

        logger.debug("Normalizing form data for GPP observation creation")
        try:
            normalized_data = {
                key: self._normalize(value) for key, value in request.data.items()
            }
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION, error=e, previous_messages=messages
            )
        messages.append(
            StageMessage(
                stage=Stage.NORMALIZATION,
                status=MessageStatus.SUCCESS,
                message="Form data normalized successfully.",
            )
        )

        logger.debug("Serializing data for GPP observation creation")
        try:
            # Setup client to communicate with GPP.
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)

            # Validate and extract required IDs for observation creation.
            context_serializer = ContextSerializer(data=normalized_data)
            context_serializer.is_valid(raise_exception=True)
            gpp_target_id = context_serializer.gpp_target_id
            gpp_observation_id = context_serializer.gpp_observation_id
            goats_target = context_serializer.goats_target
            instrument = context_serializer.instrument

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

        # Create target.
        logger.debug("Creating sidereal target in GPP")
        try:
            clone_target_result = async_to_sync(client.target.clone)(
                target_id=gpp_target_id, properties=target_properties
            )
            new_target_id = clone_target_result.get("newTarget", {}).get("id")

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

        # Create observation.
        logger.debug("Creating observation in GPP")
        try:
            observation_properties.target_environment = TargetEnvironmentInput(
                asterism=[new_target_id]
            )

            clone_observation_result = async_to_sync(client.observation.clone)(
                observation_id=gpp_observation_id, properties=observation_properties
            )
            new_observation = clone_observation_result.get("newObservation", {})
            new_observation_id = new_observation.get("id")

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
        logger.debug("Setting workflow state for new GPP observation")
        try:
            new_workflow_state = self._set_workflow_state_with_retry(
                client=client,
                observation_id=new_observation_id,
                workflow_state=workflow_state,
            )
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SUCCESS,
                    message=f"Workflow state set to {new_workflow_state['state']}.",
                )
            )

        except Exception as e:
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.ERROR,
                    message=str(e),
                )
            )

        # Save the created observation to GOATS database.
        logger.debug("Creating GOATS observation record")
        try:
            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                observation=new_observation,
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

        return self._build_structured_response(messages=messages, data=data)

    def _set_workflow_state_with_retry(
        self,
        client: GPPClient,
        observation_id: str,
        workflow_state: ObservationWorkflowState,
        *,
        max_attempts: int = 55,
        initial_delay: float = 5.0,
        retry_delay: float = 1.0,
    ) -> dict[str, Any]:
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

        Returns
        -------
        dict[str, Any]
            The result of the successful workflow state update.

        Raises
        ------
        RuntimeError
            If the workflow state could not be set after all retry attempts.
        ValueError
            If the requested transition is invalid (non-retryable).
        Exception
            If a non-retryable error occurs.
        """
        # Initial delay before starting attempts since we know the observation won't be
        # ready immediately.
        time.sleep(initial_delay)

        for attempt in range(1, max_attempts + 1):
            try:
                result = async_to_sync(client.workflow_state.update_by_id)(
                    observation_id=observation_id,
                    workflow_state=workflow_state,
                )
                return result
            except RuntimeError:
                # This is the only retryable case: calculation state not READY.
                logger.debug(
                    "Attempt %d/%d: Observation %s not ready "
                    "for workflow state change. Retrying in %.1f seconds...",
                    attempt,
                    max_attempts,
                    observation_id,
                    retry_delay,
                )
                time.sleep(retry_delay)
            except ValueError:
                # Invalid transition, do not retry.
                raise
            except Exception:
                # All other exceptions are treated as non-retryable.
                raise

        raise RuntimeError("Failed to set workflow state after multiple retries.")

    def _create_goats_observation(
        self,
        request: Request,
        target_id: int,
        instrument: str,
        observation: dict[str, Any],
        facility: str = "GEM",
    ) -> Response:
        """
        Save the created GPP observation to the GOATS database using the TOM API
        view.

        Parameters
        ----------
        request : Request
            The DRF request object.
        target_id : int
            The ID of the GOATS target to associate with the observation.
        instrument : str
            The observation type (e.g., "GMOS_SOUTH_LONG_SLIT").
        observation : dict[str, Any]
            The observation data returned from GPP.
        facility : str, default="GEM"
            The facility name.

        Returns
        -------
        Response
            The DRF response from the TOM ObservationRecordViewSet.
        """
        # Inject required fields into observation parameters.
        observation.update(
            {
                "target_id": target_id,
                "facility": facility,
            }
        )
        # 'observing_parameters' expects a payload matching the return of gpp-client.
        payload = {
            "target_id": target_id,
            "facility": facility,
            "observation_type": instrument,
            "observing_parameters": observation,
        }

        # Use APIRequestFactory to build an internal POST request.
        factory = APIRequestFactory()
        internal_request = factory.post("/api/observations/", payload, format="json")
        internal_request.user = request.user

        # Dispatch request to TOM view.
        view = ObservationRecordViewSet.as_view({"post": "create"})
        return view(internal_request)

    def _build_structured_response(
        self,
        messages: List[StageMessage],
        data: dict[str, Any],
        status_code: int = status.HTTP_201_CREATED,
    ) -> Response:
        """
        Build a structured response from the given messages and data.

        Parameters
        ----------
        messages : list[StageMessage]
            The list of stage messages.
        data : dict[str, Any]
            The data to include in the response.
        status_code : int = status.HTTP_201_CREATED
            The HTTP status code for the response.

        Returns
        -------
        Response
            The structured response.
        """
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
