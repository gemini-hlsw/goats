"""Tests for GPPTooViewSet."""

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from unittest.mock import AsyncMock
from gpp_client.api.input_types import ObservationPropertiesInput, TargetPropertiesInput
from gpp_client.api.enums import ObservationWorkflowState
from goats_tom.tests.factories import UserFactory, GPPLoginFactory
from goats_tom.api_views import GPPTooViewSet


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
        assert response.data["detail"] == "GPP login credentials are not configured for this user."

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
        mock_client.workflow_state.get_by_id = AsyncMock(return_value={"state": "ONGOING"})
        mock_client.workflow_state.update_by_id = AsyncMock(return_value={"state": "READY"})

        viewset = GPPTooViewSet()

        get_result = viewset._get_workflow_state(mock_client, observation_id="o-1")
        set_result = viewset._set_workflow_state(
            mock_client,
            workflow_state=ObservationWorkflowState.READY,
            observation_id="o-1",
        )

        assert get_result == {"state": "ONGOING"}
        assert set_result == {"state": "READY"}
        mock_client.workflow_state.get_by_id.assert_awaited_once_with(observation_id="o-1")
        mock_client.workflow_state.update_by_id.assert_awaited_once_with(
            workflow_state=ObservationWorkflowState.READY, observation_id="o-1"
        )

    @pytest.mark.parametrize(
        "method_name",
        [
            "_format_observation_properties",
            "_format_target_properties",
            "_format_workflow_state_properties",
        ],
    )
    def test_not_implemented_methods(self, method_name: str) -> None:
        """Ensure NotImplementedError is raised for unimplemented methods."""
        viewset = GPPTooViewSet()
        with pytest.raises(NotImplementedError):
            getattr(viewset, method_name)({})
