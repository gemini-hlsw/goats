"""Tests for GPPTooViewSet."""

from unittest.mock import AsyncMock

import pytest
from gpp_client.api.enums import ObservationWorkflowState
from gpp_client.api.input_types import (
    AirMassRangeInput,
    BandBrightnessIntegratedInput,
    ElevationRangeInput,
    ExposureTimeModeInput,
    HourAngleRangeInput,
    ObservationPropertiesInput,
    TargetPropertiesInput,
    SourceProfileInput,
    ObservingModeInput
)
from rest_framework import status, serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPTooViewSet
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.django_db
class TestGPPTooViewSet:
    """Tests for creating ToOs with GPP."""

    def setup_method(self) -> None:
        """Setup common test resources."""
        self.factory = APIRequestFactory()
        self.create_view = GPPTooViewSet.as_view({"post": "create"})
        self.url = "/api/gpp/too/"

        # Users
        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_create_too_missing_gpplogin(self) -> None:
        """Return 400 if the user has no GPP credentials."""
        request = self.factory.post(self.url, {})
        force_authenticate(request, user=self.user_without_login)

        response = self.create_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_create_too_success(self, mocker) -> None:
        """Initialize GPPClient successfully and return placeholder response."""
        mock_client = mocker.patch("goats_tom.api_views.gpp.toos.GPPClient")

        request = self.factory.post(self.url, {"example": "data"})
        force_authenticate(request, user=self.user_with_login)

        response = self.create_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"detail": "Not yet implemented."}
        mock_client.assert_called_once()

    def test_create_too_client_init_error(self, mocker) -> None:
        """Handle initialization failure of GPPClient gracefully."""
        mocker.patch(
            "goats_tom.api_views.gpp.toos.GPPClient",
            side_effect=RuntimeError("Bad token"),
        )

        request = self.factory.post(self.url, {})
        force_authenticate(request, user=self.user_with_login)

        response = self.create_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Bad token" in response.data["detail"]

    def test_clone_target_invokes_client(self, mocker) -> None:
        """Ensure _clone_target calls the async client method."""
        mock_client = mocker.MagicMock()
        mock_client.target.clone = AsyncMock(return_value={"id": "t-123"})

        viewset = GPPTooViewSet()
        result = viewset._clone_target(
            mock_client, properties=TargetPropertiesInput(), target_id="t-123"
        )

        assert result == {"id": "t-123"}
        mock_client.target.clone.assert_awaited_once_with(
            target_id="t-123", properties=TargetPropertiesInput()
        )

    def test_clone_observation_invokes_client(self, mocker) -> None:
        """Ensure _clone_observation calls the async client method."""
        mock_client = mocker.MagicMock()
        mock_client.observation.clone = AsyncMock(return_value={"id": "o-456"})

        viewset = GPPTooViewSet()
        result = viewset._clone_observation(
            mock_client, properties=ObservationPropertiesInput(), observation_id="o-456"
        )

        assert result == {"id": "o-456"}
        mock_client.observation.clone.assert_awaited_once_with(
            observation_id="o-456", properties=ObservationPropertiesInput()
        )

    def test_workflow_state_methods(self, mocker) -> None:
        """Ensure _get_workflow_state and _set_workflow_state call async methods."""
        mock_client = mocker.MagicMock()
        mock_client.workflow_state.get_by_id = AsyncMock(
            return_value={"state": "ONGOING"}
        )
        mock_client.workflow_state.update_by_id = AsyncMock(
            return_value={"state": "READY"}
        )

        viewset = GPPTooViewSet()

        get_result = viewset._get_workflow_state(mock_client, observation_id="o-1")
        set_result = viewset._set_workflow_state(
            mock_client,
            workflow_state=ObservationWorkflowState.READY,
            observation_id="o-1",
        )

        assert get_result == {"state": "ONGOING"}
        assert set_result == {"state": "READY"}
        mock_client.workflow_state.get_by_id.assert_awaited_once_with(
            observation_id="o-1"
        )
        mock_client.workflow_state.update_by_id.assert_awaited_once_with(
            workflow_state=ObservationWorkflowState.READY, observation_id="o-1"
        )

    def test_format_brightnesses_properties_valid_data(self, mocker) -> None:
        """Test _format_brightnesses_properties with valid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.BrightnessesSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = {
            "brightnesses": [{"band": "V", "value": 12.3}]
        }

        viewset = GPPTooViewSet()
        result = viewset._format_brightnesses_properties(
            {"brightnesses": [{"band": "V", "value": 12.3}]}
        )

        assert result == [BandBrightnessIntegratedInput(band="V", value=12.3)]
        mock_serializer.assert_called_once_with(
            data={"brightnesses": [{"band": "V", "value": 12.3}]}
        )
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_brightnesses_properties_no_data(self, mocker) -> None:
        """Test _format_brightnesses_properties with no brightnesses data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.BrightnessesSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = {}

        viewset = GPPTooViewSet()
        result = viewset._format_brightnesses_properties({})

        assert result is None
        mock_serializer.assert_called_once_with(data={})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_brightnesses_properties_invalid_data(self, mocker) -> None:
        """Test _format_brightnesses_properties with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.BrightnessesSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_brightnesses_properties({"brightnesses": [{"band": "V"}]})

        mock_serializer.assert_called_once_with(data={"brightnesses": [{"band": "V"}]})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_exposure_mode_properties_valid_data(self, mocker) -> None:
        """Test _format_exposure_mode_properties with valid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ExposureModeSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = {"mode": "EXPOSURE"}

        viewset = GPPTooViewSet()
        result = viewset._format_exposure_mode_properties({"mode": "EXPOSURE"})

        assert result == ExposureTimeModeInput(mode="EXPOSURE")
        mock_serializer.assert_called_once_with(data={"mode": "EXPOSURE"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_exposure_mode_properties_no_data(self, mocker) -> None:
        """Test _format_exposure_mode_properties with no exposure mode data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ExposureModeSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = {}

        viewset = GPPTooViewSet()
        result = viewset._format_exposure_mode_properties({})

        assert result is None
        mock_serializer.assert_called_once_with(data={})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_exposure_mode_properties_invalid_data(self, mocker) -> None:
        """Test _format_exposure_mode_properties with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ExposureModeSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_exposure_mode_properties({"mode": "INVALID"})

        mock_serializer.assert_called_once_with(data={"mode": "INVALID"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_elevation_range_properties_valid_air_mass(self, mocker) -> None:
        """Test _format_elevation_range_properties with valid air mass data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ElevationRangeSerializer"
        )
        mock_instance = mock_serializer.return_value
        mock_instance.is_valid.return_value = True
        mock_instance.validated_data = {"airMass": {"min": 1.0, "max": 2.0}}

        viewset = GPPTooViewSet()
        result = viewset._format_elevation_range_properties(
            {"airMassMinimumInput": "1.0", "airMassMaximumInput": "2.0"}
        )

        assert result == ElevationRangeInput(
            airMass=AirMassRangeInput(min=1.0, max=2.0), hourAngle=None
        )
        mock_serializer.assert_called_once_with(
            data={"airMassMinimumInput": "1.0", "airMassMaximumInput": "2.0"}
        )
        mock_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_elevation_range_properties_valid_hour_angle(self, mocker) -> None:
        """Test _format_elevation_range_properties with valid hour angle data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ElevationRangeSerializer"
        )
        mock_instance = mock_serializer.return_value
        mock_instance.is_valid.return_value = True
        mock_instance.validated_data = {
            "hourAngle": {"minHours": -2.0, "maxHours": 2.0}
        }

        viewset = GPPTooViewSet()
        result = viewset._format_elevation_range_properties(
            {"haMinimumInput": "-2.0", "haMaximumInput": "2.0"}
        )

        assert result == ElevationRangeInput(
            hourAngle=HourAngleRangeInput(minHours=-2.0, maxHours=2.0), airMass=None
        )
        mock_serializer.assert_called_once_with(
            data={"haMinimumInput": "-2.0", "haMaximumInput": "2.0"}
        )
        mock_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_elevation_range_properties_empty(self, mocker) -> None:
        """Test _format_elevation_range_properties with no elevation range data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ElevationRangeSerializer"
        )
        mock_instance = mock_serializer.return_value
        mock_instance.is_valid.return_value = True
        mock_instance.validated_data = {}

        viewset = GPPTooViewSet()
        result = viewset._format_elevation_range_properties({})

        assert result is None
        mock_serializer.assert_called_once_with(data={})
        mock_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_elevation_range_properties_invalid_data(self, mocker) -> None:
        """Test _format_elevation_range_properties with invalid elevation range data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ElevationRangeSerializer"
        )
        mock_instance = mock_serializer.return_value
        mock_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_elevation_range_properties({"haMinimumInput": "bad"})

        mock_serializer.assert_called_once_with(data={"haMinimumInput": "bad"})
        mock_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_source_profile_properties_valid_data(self, mocker) -> None:
        """Test _format_source_profile_properties with valid data."""
        data = {"point": {
                    "bandNormalized": {"sed": {"mocked": "data"}}
                }}
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.SourceProfileSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = data

        viewset = GPPTooViewSet()
        result = viewset._format_source_profile_properties(data)

        assert result == SourceProfileInput(**data)
        mock_serializer.assert_called_once_with(data=data)
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_source_profile_properties_invalid_data(self, mocker) -> None:
        """Test _format_source_profile_properties with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.SourceProfileSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_source_profile_properties({"profile": "INVALID"})

        mock_serializer.assert_called_once_with(data={"profile": "INVALID"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_clone_observation_input_invalid_data(self, mocker) -> None:
        """Test _format_clone_observation_input with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.CloneObservationSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_clone_observation_input({"field": "invalid"})

        mock_serializer.assert_called_once_with(data={"field": "invalid"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_clone_target_input_invalid_data(self, mocker) -> None:
        """Test _format_clone_target_input with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.CloneTargetSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_clone_target_input({"field": "invalid"})

        mock_serializer.assert_called_once_with(data={"field": "invalid"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_workflow_state_properties_valid_data(self, mocker) -> None:
        """Test _format_workflow_state_properties with valid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.WorkflowStateSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.workflow_state_enum = ObservationWorkflowState.READY

        viewset = GPPTooViewSet()
        result = viewset._format_workflow_state_properties({"state": "READY"})

        assert result == ObservationWorkflowState.READY
        mock_serializer.assert_called_once_with(data={"state": "READY"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_workflow_state_properties_no_data(self, mocker) -> None:
        """Test _format_workflow_state_properties with no workflow state data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.WorkflowStateSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.workflow_state_enum = None

        viewset = GPPTooViewSet()
        result = viewset._format_workflow_state_properties({})

        assert result is None
        mock_serializer.assert_called_once_with(data={})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_workflow_state_properties_invalid_data(self, mocker) -> None:
        """Test _format_workflow_state_properties with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.WorkflowStateSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_workflow_state_properties({"state": "INVALID"})

        mock_serializer.assert_called_once_with(data={"state": "INVALID"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_observing_mode_properties_no_data(self, mocker) -> None:
        """Test _format_observing_mode_properties with no observing mode data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ObservingModeSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.validated_data = {}

        viewset = GPPTooViewSet()
        result = viewset._format_observing_mode_properties({})

        assert result == ObservingModeInput()
        mock_serializer.assert_called_once_with(data={})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)

    def test_format_observing_mode_properties_invalid_data(self, mocker) -> None:
        """Test _format_observing_mode_properties with invalid data."""
        mock_serializer = mocker.patch(
            "goats_tom.api_views.gpp.toos.ObservingModeSerializer"
        )
        mock_serializer_instance = mock_serializer.return_value
        mock_serializer_instance.is_valid.side_effect = serializers.ValidationError

        viewset = GPPTooViewSet()
        with pytest.raises(serializers.ValidationError):
            viewset._format_observing_mode_properties({"mode": "INVALID"})

        mock_serializer.assert_called_once_with(data={"mode": "INVALID"})
        mock_serializer_instance.is_valid.assert_called_once_with(raise_exception=True)
