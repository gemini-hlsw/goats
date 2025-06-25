from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import GOALoginFactory, UserFactory


class TestGOAQueryFormView(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up the necessary objects for testing."""
        cls.client = Client()
        cls.user = UserFactory(username="testuser", password="password")
        cls.target = SiderealTargetFactory.create()
        cls.observation_record = ObservingRecordFactory.create(
            target_id=cls.target.id, status="Observed"
        )
        cls.url = reverse("goa_query", kwargs={"pk": cls.observation_record.pk})
        cls.form_data = {"download_calibrations": "yes", "facility": "test_facility"}

    @patch("goats_tom.views.goa_query_form.GOA")
    @patch("goats_tom.views.goa_query_form.download_goa_files.send")
    def test_successful_submission(self, mock_download, mock_goa):
        """Test successful form submission with valid GOA credentials."""
        GOALoginFactory.create(
            user=self.user, username="goauser", password="goapassword",
        )
        self.client.login(username="testuser", password="password")

        response = self.client.post(self.url, self.form_data)

        self.assertEqual(response.status_code, 302)
        mock_download.assert_called_once()
        messages = [msg.message for msg in get_messages(response.wsgi_request)]
        self.assertIn("Downloading data in background. Check back soon!", messages)

    @patch("goats_tom.views.goa_query_form.GOA")
    @patch("goats_tom.views.goa_query_form.download_goa_files.send")
    def test_missing_goa_credentials(self, mock_download, mock_goa):
        """Test form submission with missing GOA credentials."""
        self.client.login(username="testuser", password="password")

        response = self.client.post(self.url, self.form_data)

        self.assertEqual(response.status_code, 302)
        mock_download.assert_called_once()
        messages = [msg.message for msg in get_messages(response.wsgi_request)]
        self.assertIn(
            "GOA login credentials not found. Proprietary data will not be downloaded.",
            messages,
        )

    @patch("goats_tom.views.goa_query_form.GOA")
    @patch("goats_tom.views.goa_query_form.download_goa_files.send")
    def test_failed_goa_authentication(self, mock_download, mock_goa):
        """Test form submission with failed GOA authentication."""
        GOALoginFactory.create(
            user=self.user, username="goauser", password="goapassword",
        )
        self.client.login(username="testuser", password="password")

        # Mock GOA authentication failure
        mock_goa.authenticated.return_value = False

        response = self.client.post(self.url, self.form_data)

        self.assertEqual(response.status_code, 302)
        mock_download.assert_called_once()
        messages_list = [msg.message for msg in get_messages(response.wsgi_request)]
        self.assertIn(
            "GOA login failed. Re-enter login credentials. "
            "Proprietary data will not be downloaded.",
            messages_list,
        )

    def test_handling_of_form_errors(self):
        """Test handling of form errors."""
        self.client.login(username="testuser", password="password")

        # Provide partially invalid form data
        form_data = {"query_params": ""}
        response = self.client.post(self.url, form_data)
        self.assertEqual(response.status_code, 302)
