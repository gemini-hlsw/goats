from unittest.mock import patch
from goats_tom.tests.factories import UserFactory
from django.test import TestCase
from django.urls import reverse
from goats_tom.models import LCOLogin
from goats_tom.views import LCOLoginView

class TestLCOLoginView(TestCase):
    def setUp(self):
        self.user = UserFactory(username="testuser", password="secret")
        self.client.force_login(user=self.user)
        self.url = reverse("user-lco-login", kwargs={"pk": self.user.pk})

    def test_get_request_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login_form.html")
        self.assertContains(response, "LCO")

    @patch.object(LCOLoginView, "perform_login_and_logout", return_value=True)
    def test_post_valid_credentials(self, mocker):
        """
        Valid credentials, login passes -> success message, credentials stored.
        """
        form_data = {"token": "1234"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(any("LCO login information verified" in str(msg) for msg in messages_list))

        login_obj = LCOLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.token, "1234")

    @patch.object(LCOLoginView, "perform_login_and_logout", return_value=False)
    def test_post_invalid_credentials(self, mock_method):
        """
        Invalid credentials -> failure message, but credentials still saved by design.
        """
        form_data = {"token": "5678"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Failed to verify LCO credentials" in str(msg) for msg in messages_list))

        login_obj = LCOLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.token, "5678")

    def test_post_form_invalid(self):
        """
        Form invalid for Astro Datalab -> re-renders with an error, no credentials saved.
        """
        form_data = {"token": ""}
        response = self.client.post(self.url, form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("Failed to save LCO login information" in str(msg)
                            for msg in response.context["messages"]))
        self.assertFalse(LCOLogin.objects.filter(user=self.user).exists())
