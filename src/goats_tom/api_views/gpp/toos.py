"""Handles creating ToOs with GPP."""

__all__ = ["GPPTooViewSet"]

from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.enums import ObservationWorkflowState
from gpp_client.api.input_types import (
    BandBrightnessIntegratedInput,
    CloneObservationInput,
    CloneTargetInput,
    ElevationRangeInput,
    ExposureTimeModeInput,
    ObservationPropertiesInput,
    ObservingModeInput,
    SiderealInput,
    SourceProfileInput,
    TargetPropertiesInput,
)
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins

from goats_tom.serializers.gpp import (
    BrightnessesSerializer,
    CloneObservationSerializer,
    CloneTargetSerializer,
    ElevationRangeSerializer,
    ExposureModeSerializer,
    ObservingModeSerializer,
    SiderealSerializer,
    SourceProfileSerializer,
    WorkflowStateSerializer,
)


class GPPTooViewSet(GenericViewSet, mixins.CreateModelMixin):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

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

        try:
            # Setup client to communicate with GPP.
            _ = GPPClient(url=settings.GPP_URL, token=credentials.token)

            # We want to setup all the formatting and mutations first, for validation,
            # before making any changes in GPP.
            """
            clone_target_input = self._format_clone_target_input(request.data)

            clone_observation_input = self._format_clone_observation_input(request.data)

            set_workflow_state_input = self._format_workflow_state_properties(
                request.data
            )
            """

            return Response({"detail": "Not yet implemented."})

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _format_source_profile_properties(
        self, data: dict[str, Any]
    ) -> SourceProfileInput:
        """
        Format source profile properties from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing source profile fields.

        Returns
        -------
        SourceProfileInput
            A SourceProfileInput instance.

        Raises
        ------
        serializers.ValidationError
            If any error occurs during parsing or validation of source profile values.
        """
        source_profile_serializer = SourceProfileSerializer(data=data)
        source_profile_serializer.is_valid(raise_exception=True)
        return SourceProfileInput(**source_profile_serializer.validated_data)

    def _format_observing_mode_properties(
        self, data: dict[str, Any]
    ) -> ObservingModeInput:
        """Format observing mode-specific properties from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing observing mode fields.

        Returns
        -------
        ObservingModeInput
            An ObservingModeInput instance.
        """
        observing_mode_serializer = ObservingModeSerializer(data=data)
        observing_mode_serializer.is_valid(raise_exception=True)
        return ObservingModeInput(**observing_mode_serializer.validated_data)

    def _format_workflow_state_properties(
        self, data: dict[str, Any]
    ) -> ObservationWorkflowState | None:
        """Format workflow state property from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing workflow state fields.

        Returns
        -------
        ObservationWorkflowState | None
            An ObservationWorkflowState enum instance or ``None`` if no workflow
            state is provided.

        Raises
        ------
        serializers.ValidationError
            If any error occurs during parsing or validation of workflow state values.
        """
        workflow_state_serializer = WorkflowStateSerializer(data=data)
        workflow_state_serializer.is_valid(raise_exception=True)
        return workflow_state_serializer.workflow_state_enum

    def _format_elevation_range_properties(
        self, data: dict[str, Any]
    ) -> ElevationRangeInput | None:
        """Format elevation range properties from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing elevation range fields.

        Returns
        -------
        ElevationRangeInput | None
            An ElevationRangeInput instance or ``None`` if no elevation range is
            provided.

        Raises
        ------
        serializers.ValidationError
            If any error occurs during parsing or validation of elevation range values.
        """

        elevation_range = ElevationRangeSerializer(data=data)
        elevation_range.is_valid(raise_exception=True)
        return (
            ElevationRangeInput(**elevation_range.validated_data)
            if elevation_range.validated_data
            else None
        )

    def _format_brightnesses_properties(
        self, data: dict[str, Any]
    ) -> list[BandBrightnessIntegratedInput] | None:
        """Format brightnesses properties from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing brightness fields.

        Returns
        -------
        list[BandBrightnessIntegratedInput] | None
            A list of BandBrightnessIntegratedInput instances or ``None`` if no
            brightnesses are provided.

        Raises
        ------
        serializers.ValidationError
            If any error occurs during parsing or validation of brightness values.
        """
        brightnesses = BrightnessesSerializer(data=data)
        brightnesses.is_valid(raise_exception=True)
        brightnesses_data = brightnesses.validated_data.get("brightnesses", None)
        return (
            [BandBrightnessIntegratedInput(**b) for b in brightnesses_data]
            if brightnesses_data
            else None
        )

    def _format_exposure_mode_properties(
        self, data: dict[str, Any]
    ) -> ExposureTimeModeInput | None:
        """Format exposure mode properties from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing exposure mode fields.

        Returns
        -------
        ExposureTimeModeInput | None
            An ExposureTimeModeInput instance or ``None`` if no exposure mode is
            provided.

        Raises
        ------
        serializers.ValidationError
            If any error occurs during parsing or validation of exposure mode values.
        """

        exposure_mode = ExposureModeSerializer(data=data)
        exposure_mode.is_valid(raise_exception=True)
        return (
            ExposureTimeModeInput(**exposure_mode.validated_data)
            if exposure_mode.validated_data
            else None
        )

    def _clone_target(
        self, client: GPPClient, properties: TargetPropertiesInput, target_id: str
    ) -> dict[str, Any]:
        """Clone a target in GPP with new properties.

        Parameters
        ----------
        client : GPPClient
            An authenticated GPP client instance.
        properties : TargetPropertiesInput
            The new properties for the cloned target.
        target_id : str
            The ID of the target to clone.

        Returns
        -------
        dict[str, Any]
            The newly created target's details.
        """
        return async_to_sync(client.target.clone)(
            target_id=target_id, properties=properties
        )

    def _clone_observation(
        self,
        client: GPPClient,
        properties: ObservationPropertiesInput,
        observation_id: str,
    ) -> dict[str, Any]:
        """Clone an observation in GPP with new properties.

        Parameters
        ----------
        client : GPPClient
            An authenticated GPP client instance.
        properties : ObservationPropertiesInput
            The new properties for the cloned observation.
        observation_id : str
            The ID of the observation to clone.

        Returns
        -------
        dict[str, Any]
            The newly created observation's details.
        """
        return async_to_sync(client.observation.clone)(
            observation_id=observation_id, properties=properties
        )

    def _format_clone_observation_input(
        self, data: dict[str, Any]
    ) -> CloneObservationInput:
        """Format the clone observation input from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing observation fields.

        Returns
        -------
        CloneObservationInput
            The formatted clone observation input.
        """
        print("Starting _format_clone_observation_input")

        clone_observation = CloneObservationSerializer(data=data)
        clone_observation.is_valid(raise_exception=True)
        print("CloneObservationSerializer validated successfully")

        observing_mode = self._format_observing_mode_properties(data)
        print("Observing mode properties formatted successfully")

        elevation_range = self._format_elevation_range_properties(data)
        print("Elevation range properties formatted successfully")

        exposure_mode = self._format_exposure_mode_properties(data)
        print("Exposure mode properties formatted successfully")

        observation_properties = ObservationPropertiesInput(
            **clone_observation.validated_data
        )
        print("ObservationPropertiesInput created successfully")

        observation_properties.constraint_set.elevation_range = elevation_range
        print("Elevation range set successfully")

        observation_properties.observing_mode = observing_mode
        print("Observing mode set successfully")

        observation_properties.science_requirements.exposure_time_mode = exposure_mode
        print("Exposure time mode set successfully")

        print("Finished _format_clone_observation_input")
        return CloneObservationInput(
            observation_id=clone_observation.observation_id, set=observation_properties
        )

    def _format_clone_target_input(self, data: dict[str, Any]) -> CloneTargetInput:
        """Format the target input from the request data and other payloads.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing target fields.

        Returns
        -------
        CloneTargetInput
            The formatted clone target input.
        """
        clone_target = CloneTargetSerializer(data=data)
        clone_target.is_valid(raise_exception=True)

        source_profile = self._format_source_profile_properties(data)
        brightnesses = self._format_brightnesses_properties(data)
        source_profile.point.band_normalized.brightnesses = brightnesses
        sidereal = self._format_sidereal_target_input(data)

        target_properties = TargetPropertiesInput(
            sidereal=sidereal,
            source_profile=source_profile,
        )

        return CloneTargetInput(target_id=clone_target.target_id, set=target_properties)

    def _format_sidereal_target_input(self, data: dict[str, Any]) -> SiderealInput:
        """Format the sidereal target input from the request data.

        Parameters
        ----------
        data : dict[str, Any]
            The request data containing sidereal target fields.

        Returns
        -------
        SiderealInput
            The formatted sidereal target input.
        """
        sidereal_properties = SiderealSerializer(data=data)
        sidereal_properties.is_valid(raise_exception=True)
        return SiderealInput(**sidereal_properties.validated_data)

    def _get_workflow_state(
        self, client: GPPClient, observation_id: str
    ) -> dict[str, Any]:
        """Retrieve the workflow state for a given observation.

        Parameters
        ----------
        client : GPPClient
            An authenticated GPP client instance.
        observation_id : str
            The ID of the observation to retrieve the workflow state for.

        Returns
        -------
        dict[str, Any]
            The workflow state details.
        """
        return async_to_sync(client.workflow_state.get_by_id)(
            observation_id=observation_id
        )

    def _set_workflow_state(
        self,
        client: GPPClient,
        workflow_state: ObservationWorkflowState,
        observation_id: str,
    ) -> dict[str, Any]:
        """Set the workflow state for a given observation.

        Parameters
        ----------
        client : GPPClient
            An authenticated GPP client instance.
        workflow_state : ObservationWorkflowState
            The new workflow state to set.
        observation_id : str
            The ID of the observation to set the workflow state for.

        Returns
        -------
        dict[str, Any]
            The updated workflow state details.
        """
        return async_to_sync(client.workflow_state.update_by_id)(
            workflow_state=workflow_state, observation_id=observation_id
        )
