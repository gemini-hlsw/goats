from unittest.mock import MagicMock, patch

import requests
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import GOALoginFactory, UserFactory

ARCHIVE_URL = "https://archive.gemini.edu/searchform/GS-2024A-Q-1"


class TestGOAArchiveRedirectView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = UserFactory(username="testuser", password="password")
        cls.target = SiderealTargetFactory.create()
        cls.observation_record = ObservingRecordFactory.create(
            target_id=cls.target.id, status="Observed"
        )
        cls.url = reverse(
            "goa-archive-redirect", kwargs={"pk": cls.observation_record.pk}
        )

    def setUp(self):
        self.client.login(username="testuser", password="password")

    def _mock_record(self, url=ARCHIVE_URL):
        mock = MagicMock()
        mock.url = url
        return mock

    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_no_archive_url_redirects_to_observation(self, mock_get):
        """Observation with no URL redirects back to observation detail."""
        mock_get.return_value = self._mock_record(url="")

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("tom_observations:detail", kwargs={"pk": self.observation_record.pk}),
            fetch_redirect_response=False,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("No archive URL available for this observation.", messages)

    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_200_redirects_to_archive(self, mock_get, mock_head):
        """When archive responds 200, redirects directly to archive URL."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 200

        response = self.client.get(self.url)

        self.assertRedirects(response, ARCHIVE_URL, fetch_redirect_response=False)

    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_302_redirects_to_archive(self, mock_get, mock_head):
        """When archive responds 302, redirects directly to archive URL."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 302

        response = self.client.get(self.url)

        self.assertRedirects(response, ARCHIVE_URL, fetch_redirect_response=False)

    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_archive_not_responding_shows_message(self, mock_get, mock_head):
        """When archive request raises an exception, shows message on observation page."""
        mock_get.return_value = self._mock_record()
        mock_head.side_effect = requests.RequestException("timeout")

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("tom_observations:detail", kwargs={"pk": self.observation_record.pk}),
            fetch_redirect_response=False,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("The Gemini Observatory Archive is not responding.", messages)

    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_403_without_credentials_redirects_to_goats_login(self, mock_get, mock_head):
        """When archive returns 403 and user has no credentials, redirects to GOATS GOA login."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 403

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("user-goa-login", kwargs={"pk": self.user.pk}),
            fetch_redirect_response=False,
        )

    @patch("goats_tom.views.goa_archive_redirect.GOA")
    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_403_with_valid_credentials_renders_login_template(
        self, mock_get, mock_head, mock_goa
    ):
        """When archive returns 403 and credentials are valid, renders auto-submit template."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 403
        mock_goa.authenticated.return_value = True
        GOALoginFactory.create(user=self.user, username="goauser", password="goapass")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tom_observations/goa_archive_login.html")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertContains(response, "goauser")

    @patch("goats_tom.views.goa_archive_redirect.GOA")
    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_403_with_invalid_credentials_redirects_to_goats_login(
        self, mock_get, mock_head, mock_goa
    ):
        """When archive returns 403 and credentials are invalid, redirects to GOATS GOA login."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 403
        mock_goa.authenticated.return_value = False
        GOALoginFactory.create(user=self.user, username="goauser", password="badpass")

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("user-goa-login", kwargs={"pk": self.user.pk}),
            fetch_redirect_response=False,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Your GOA credentials are invalid. Please update them.", messages)

    @patch("goats_tom.views.goa_archive_redirect.requests.head")
    @patch("goats_tom.views.goa_archive_redirect.get_object_or_404")
    def test_other_status_shows_message_on_observation_page(self, mock_get, mock_head):
        """When archive returns an unexpected status, shows message on observation page."""
        mock_get.return_value = self._mock_record()
        mock_head.return_value.status_code = 500

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("tom_observations:detail", kwargs={"pk": self.observation_record.pk}),
            fetch_redirect_response=False,
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("The Gemini Observatory Archive is not available.", messages)
