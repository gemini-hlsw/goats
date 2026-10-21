"""Test module for the SystemViewSet."""

import signal
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from goats_tom.api_views import SystemViewSet
from goats_tom.tests.factories import UserFactory


class TestSystemViewSet(APITestCase):
    """Class to test the `SystemViewSet` API view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = UserFactory(is_superuser=True)
        self.view = SystemViewSet.as_view({"post": "shutdown"})

    def authenticate(self, request):
        force_authenticate(request, user=self.user)

    @patch("goats_tom.api_views.system.os.kill")
    def test_shutdown_unauthenticated(self, mock_kill):
        """Test that unauthenticated requests cannot shut down."""
        request = self.factory.post(reverse("system-shutdown"))
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_kill.assert_not_called()

    @patch("goats_tom.api_views.system.os.kill")
    def test_shutdown_non_admin(self, mock_kill):
        """Test that a signed-in user who is not an admin cannot shut down."""
        request = self.factory.post(reverse("system-shutdown"))
        force_authenticate(request, user=UserFactory())
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_kill.assert_not_called()

    @patch("goats_tom.api_views.system.os.kill")
    def test_shutdown_pid_file_found(self, mock_kill):
        """Test that shutdown sends SIGINT to the PID in the file and returns 200."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pid_file = Path(tmp_dir) / "goats.pid"
            pid_file.write_text("12345")

            with patch(
                "goats_tom.api_views.system.tempfile.gettempdir",
                return_value=tmp_dir,
            ):
                request = self.factory.post(reverse("system-shutdown"))
                self.authenticate(request)
                response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "shutdown initiated")
        mock_kill.assert_called_once_with(12345, signal.SIGINT)

    def test_shutdown_pid_file_not_found(self):
        """Test that shutdown returns 503 when the PID file does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "goats_tom.api_views.system.tempfile.gettempdir",
                return_value=tmp_dir,
            ):
                request = self.factory.post(reverse("system-shutdown"))
                self.authenticate(request)
                response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("error", response.data)
