"""Handles creating ToOs with GPP."""

__all__ = ["GPPTooViewSet"]


from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.input_types import TargetEnvironmentInput
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

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
        credentials = request.user.gpplogin
        normalized_data = {
            key: self._normalize(value) for key, value in request.data.items()
        }
        try:
            # Setup client to communicate with GPP.
            client = GPPClient(url=settings.GPP_URL, token=credentials.token)

            create_too_serializer = CreateTooSerializer(data=normalized_data)
            create_too_serializer.is_valid(raise_exception=True)
            gpp_target_id = create_too_serializer.gpp_target_id
            gpp_observation_id = create_too_serializer.gpp_observation_id
            goats_target = create_too_serializer.goats_target
            print(
                "\nRequired IDs for ToO creation: ",
                gpp_target_id,
                gpp_observation_id,
                goats_target.id,
            )

            target_serializer = TargetSerializer(data=normalized_data)
            target_serializer.is_valid(raise_exception=True)
            target_properties = target_serializer.to_pydantic()
            print("\nTarget 'to_pydantic()': ", target_properties)

            observation_serializer = ObservationSerializer(data=normalized_data)
            observation_serializer.is_valid(raise_exception=True)
            observation_properties = observation_serializer.to_pydantic()
            print("\nObservation 'to_pydantic()': ", observation_properties)

            workflow_state_serializer = WorkflowStateSerializer(data=normalized_data)
            workflow_state_serializer.is_valid(raise_exception=True)
            workflow_state = workflow_state_serializer.workflow_state_enum
            print("\nWorkflow state: ", workflow_state)

            print("\nValidation complete.")

            # Clone the target in GPP.
            print("\nCloning target...")
            clone_target_result = async_to_sync(client.target.clone)(
                target_id=gpp_target_id, properties=target_properties
            )
            print("\nCloned target result:", clone_target_result)

            # Get the new target ID from the clone result.
            new_target_id = clone_target_result.get("newTarget", {}).get("id")

            if new_target_id is None:
                raise ValueError("Failed to retrieve new target ID from clone result.")

            # Update observation properties to link to the new target ID.
            observation_properties.target_environment = TargetEnvironmentInput(
                asterism=[new_target_id]
            )
            print(
                "\nUpdated observation properties with new target ID:",
                observation_properties,
            )

            # Clone the observation in GPP.
            clone_observation_result = async_to_sync(client.observation.clone)(
                observation_id=gpp_observation_id, properties=observation_properties
            )
            print("\nCloned observation result:", clone_observation_result)

            # Get the new observation ID from the clone result.
            new_observation_id = clone_observation_result.get("newObservation", {}).get(
                "id"
            )
            if new_observation_id is None:
                raise ValueError(
                    "Failed to retrieve new observation ID from clone result."
                )
            print("\nNew observation ID:", new_observation_id)

            # Set the workflow state for the new observation.
            set_workflow_state_result = async_to_sync(
                client.workflow_state.update_by_id
            )(
                workflow_state=workflow_state,
                observation_id=new_observation_id,
            )
            print("\nSet workflow state result:", set_workflow_state_result)

            # TODO: Save the created ToO observation to GOATS database.
            print("\nToO creation process completed successfully.")
            print("TODO: Save the created ToO observation to GOATS database.")

            return Response({"detail": "Not yet implemented."})

        except Exception as e:
            print(str(e))
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
