from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from goats_tom.models import AstroDatalabLogin
from goats_tom.tests.factories import UserFactory
from goats_tom.views import AstroDatalabLoginView


class TestAstroDatalabLoginView(TestCase):
    """
    Tests for the AstroDatalabLoginView, which inherits from BaseLoginView.
    """

    def setUp(self) -> None:
        self.user = UserFactory(username="testuser", password="secret")
        self.client.login(username="testuser", password="secret")
        self.url = reverse("user-astro-data-lab-login", kwargs={"pk": self.user.pk})

    def test_get_request_renders_form(self):
        """
        Ensure GET request renders the login form for AstroDatalab.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login_form.html")
        self.assertContains(response, "Astro Data Lab")

    @patch.object(AstroDatalabLoginView, "perform_login_and_logout", return_value=True)
    def test_post_valid_credentials(self, mock_method):
        """
        Valid credentials, login passes -> success message, credentials stored.
        """
        form_data = {"username": "astro_user", "password": "astro_pass"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Astro Data Lab login information verified" in str(msg) for msg in messages_list))

        login_obj = AstroDatalabLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.username, "astro_user")
        self.assertEqual(login_obj.password, "astro_pass")

    @patch.object(AstroDatalabLoginView, "perform_login_and_logout", return_value=False)
    def test_post_invalid_credentials(self, mock_method):
        """
        Invalid credentials -> failure message, but credentials still saved by design.
        """
        form_data = {"username": "bad_user", "password": "bad_pass"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Failed to verify Astro Data Lab credentials" in str(msg) for msg in messages_list))

        login_obj = AstroDatalabLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.username, "bad_user")
        self.assertEqual(login_obj.password, "bad_pass")

    def test_post_form_invalid(self):
        """
        Form invalid for Astro Datalab -> re-renders with an error, no credentials saved.
        """
        form_data = {"username": ""}
        response = self.client.post(self.url, form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("Failed to save Astro Data Lab login information" in str(msg)
                            for msg in response.context["messages"]))
        self.assertFalse(AstroDatalabLogin.objects.filter(user=self.user).exists())
