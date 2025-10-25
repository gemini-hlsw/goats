"""Tests for GPPTooViewSet."""

from unittest.mock import AsyncMock

import pytest

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

    # def test_create_too_success(self, mocker) -> None:
    #     """Initialize GPPClient successfully and return placeholder response."""
    #     mock_client = mocker.patch("goats_tom.api_views.gpp.toos.GPPClient")

    #     request = self.factory.post(self.url, {"example": "data"})
    #     force_authenticate(request, user=self.user_with_login)

    #     response = self.create_view(request)

    #     assert response.status_code == status.HTTP_200_OK
    #     assert response.data == {"detail": "Not yet implemented."}
    #     mock_client.assert_called_once()

    # def test_create_too_client_init_error(self, mocker) -> None:
    #     """Handle initialization failure of GPPClient gracefully."""
    #     mocker.patch(
    #         "goats_tom.api_views.gpp.toos.GPPClient",
    #         side_effect=RuntimeError("Bad token"),
    #     )

    #     request = self.factory.post(self.url, {})
    #     force_authenticate(request, user=self.user_with_login)

    #     response = self.create_view(request)

    #     assert response.status_code == status.HTTP_400_BAD_REQUEST
    #     assert "Bad token" in response.data["detail"]

    # def test_clone_target_invokes_client(self, mocker) -> None:
    #     """Ensure _clone_target calls the async client method."""
    #     mock_client = mocker.MagicMock()
    #     mock_client.target.clone = AsyncMock(return_value={"id": "t-123"})

    #     viewset = GPPTooViewSet()
    #     result = viewset._clone_target(
    #         mock_client, properties=TargetPropertiesInput(), target_id="t-123"
    #     )

    #     assert result == {"id": "t-123"}
    #     mock_client.target.clone.assert_awaited_once_with(
    #         target_id="t-123", properties=TargetPropertiesInput()
    #     )
