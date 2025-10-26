"""Handles creating ToOs with GPP."""

__all__ = ["GPPTooViewSet"]

import time
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

from goats_tom.serializers.gpp import (
    CreateTooSerializer,
    ObservationSerializer,
    TargetSerializer,
    WorkflowStateSerializer,
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
        # Ensure the user has GPP credentials.
        if not hasattr(request.user, "gpplogin"):
            return Response(
                {"detail": "GPP login credentials are not configured for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        print("Getting GPP credentials for user:", request.user.username)
        credentials = request.user.gpplogin

        print("Normalizing request data...")
        normalized_data = {
            key: self._normalize(value) for key, value in request.data.items()
        }
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
                instrument,
            )

            print("Serializing target, observation, and workflow state...")
            # Serialize and validate target.
            target_serializer = TargetSerializer(data=normalized_data)
            target_serializer.is_valid(raise_exception=True)
            target_properties = target_serializer.to_pydantic()

            # Serialize and validate observation.
            observation_serializer = ObservationSerializer(data=normalized_data)
            observation_serializer.is_valid(raise_exception=True)
            observation_properties = observation_serializer.to_pydantic()

            # Serialize and validate workflow state.
            workflow_state_serializer = WorkflowStateSerializer(data=normalized_data)
            workflow_state_serializer.is_valid(raise_exception=True)
            workflow_state = workflow_state_serializer.workflow_state_enum

            # Clone the target in GPP.
            print("Cloning target...")
            clone_target_result = async_to_sync(client.target.clone)(
                target_id=gpp_target_id, properties=target_properties
            )

            # Get the new target ID from the clone result.
            new_target_id = clone_target_result.get("newTarget", {}).get("id")
            print("New target ID:", new_target_id)

            if new_target_id is None:
                raise ValueError("Failed to retrieve new target ID from clone result.")

            # Update observation properties to link to the new target ID.
            print("Updating observation properties with new target ID...")
            observation_properties.target_environment = TargetEnvironmentInput(
                asterism=[new_target_id]
            )

            # Clone the observation in GPP.
            print("Cloning observation...")
            clone_observation_result = async_to_sync(client.observation.clone)(
                observation_id=gpp_observation_id, properties=observation_properties
            )

            new_observation = clone_observation_result.get("newObservation", {})
            # Get the new observation ID from the clone result.
            new_observation_id = clone_observation_result.get("newObservation", {}).get(
                "id"
            )
            print("New observation ID:", new_observation_id)
            if new_observation_id is None:
                raise ValueError(
                    "Failed to retrieve new observation ID from clone result."
                )

            # Set the workflow state for the new observation, with retries.
            print("Setting workflow state for new observation...")
            self._set_workflow_state_with_retry(
                client=client,
                observation_id=new_observation_id,
                workflow_state=workflow_state,
                max_attempts=10,
                initial_delay=3.0,
                retry_delay=1.0,
            )

            # TODO: Save the created ToO observation to GOATS database.
            print("Saving ToO observation to GOATS database...")

            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                new_observation=new_observation,
            )

            # Handle TOM errors
            if tom_response.status_code != status.HTTP_201_CREATED:
                return Response(
                    {
                        "detail": (
                            "ToO created in GPP, but failed to save observation "
                            "in GOATS."
                        ),
                        "newTargetId": new_target_id,
                        "newObservationId": new_observation_id,
                        "errors": tom_response.data,
                    },
                    status=tom_response.status_code,
                )

            # All good
            return Response(
                {
                    "detail": "ToO created and saved successfully.",
                    "newTargetId": new_target_id,
                    "newObservationId": new_observation_id,
                    "goatsObservation": tom_response.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            print(str(e))
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _set_workflow_state_with_retry(
        self,
        client: GPPClient,
        observation_id: str,
        workflow_state: ObservationWorkflowState,
        *,
        max_attempts: int = 10,
        initial_delay: float = 3.0,
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
        max_attempts : int, default=10
            Maximum number of retry attempts.
        initial_delay : float, default=3.0
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
