from django.test import TestCase
from django.urls import reverse

from goats_tom.tests.factories import UserFactory


class AstroDatalabViewTest(TestCase):
    """Tests for the AstroDatalabView."""

    @classmethod
    def setUpTestData(cls):
        """Set up a test user."""
        cls.user = UserFactory()

    def test_redirects_unauthenticated_users(self):
        """Ensure unauthenticated users are redirected to login."""
        response = self.client.get(reverse("astro-data-lab"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_authenticated_user_can_access(self):
        """Ensure an authenticated user can access the page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("astro-data-lab"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "astro_datalab.html")

    def test_user_context_in_response(self):
        """Ensure the user is included in the context."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("astro-data-lab"))
        self.assertEqual(response.context["user"], self.user)
