from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse
from goats_tom.models import GOALogin
from goats_tom.views import GOALoginView


class TestGOALoginView(TestCase):
    """
    Tests for the GOALoginView, which inherits from BaseLoginView.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="secret")
        self.client.login(username="testuser", password="secret")
        self.url = reverse("user-goa-login", kwargs={"pk": self.user.pk})

    def test_get_request_renders_form(self):
        """
        Ensure GET request renders the login form.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login_form.html")
        self.assertContains(response, "GOA")
        self.assertContains(response, "username")
        self.assertContains(response, "password")

    @patch.object(GOALoginView, "perform_login_and_logout", return_value=True)
    def test_post_valid_credentials(self, mock_method):
        """
        When valid credentials are posted and login check passes,
        it should create/update GOALogin, show success message, and redirect.
        """
        form_data = {"username": "goa_user", "password": "goa_pass"}
        response = self.client.post(self.url, form_data, follow=True)

        # Check we redirected to success URL.
        self.assertRedirects(response, reverse("user-list"))
        # Check success message.
        messages_list = list(response.context["messages"])
        self.assertTrue(any("GOA login information verified" in str(msg) for msg in messages_list))

        # Check credentials saved in GOALogin model.
        login_obj = GOALogin.objects.get(user=self.user)
        self.assertEqual(login_obj.username, "goa_user")
        self.assertEqual(login_obj.password, "goa_pass")

    @patch.object(GOALoginView, "perform_login_and_logout", return_value=False)
    def test_post_invalid_credentials(self, mock_method):
        """
        If login check fails, a failure message should be displayed,
        but credentials are still saved in the model (by design).
        """
        form_data = {"username": "invalid_user", "password": "wrong_pass"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Failed to verify GOA credentials" in str(msg) for msg in messages_list))

        # Credentials are still saved (based on BaseLoginView logic).
        login_obj = GOALogin.objects.get(user=self.user)
        self.assertEqual(login_obj.username, "invalid_user")
        self.assertEqual(login_obj.password, "wrong_pass")

    def test_post_form_invalid(self):
        """
        If the form is invalid (missing fields), we expect no redirect,
        and an error message from form_invalid().
        """
        # Missing password.
        form_data = {"username": ""}
        response = self.client.post(self.url, form_data)

        # Should re-render the form with error message.
        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Failed to save GOA login information" in str(msg) for msg in messages_list))
        # Ensure nothing was saved
        self.assertFalse(GOALogin.objects.filter(user=self.user).exists())

