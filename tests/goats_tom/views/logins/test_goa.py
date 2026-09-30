from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from goats_tom.service_checks import CheckResult

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

    @patch.object(GOALoginView, "verify_credentials", return_value=CheckResult(True, "ok"))
    def test_post_valid_credentials(self, mock_method):
        """
        When valid credentials are posted and login check passes,
        it should create/update GOALogin, show success message, and redirect.
        """
        form_data = {"username": "goa_user", "password": "goa_pass"}
        response = self.client.post(self.url, form_data, follow=True)

        # Check we redirected to success URL.
        self.assertRedirects(
            response, reverse("user-update", kwargs={"pk": self.user.pk})
        )
        # Check success message.
        messages_list = list(response.context["messages"])
        self.assertTrue(any("GOA login information verified" in str(msg) for msg in messages_list))

        # Check credentials saved in GOALogin model.
        login_obj = GOALogin.objects.get(user=self.user)
        self.assertEqual(login_obj.username, "goa_user")
        self.assertEqual(login_obj.password, "goa_pass")

    @patch.object(GOALoginView, "verify_credentials", return_value=CheckResult(False, "rejected"))
    def test_post_invalid_credentials(self, mock_method):
        """
        Invalid credentials -> failure message, and nothing is written.
        """
        form_data = {"username": "invalid_user", "password": "wrong_pass"}
        response = self.client.post(self.url, form_data)

        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any(
                "Could not verify GOA credentials: GOA rejected them" in str(msg)
                for msg in messages_list
            )
        )
        self.assertFalse(GOALogin.objects.filter(user=self.user).exists())

    @patch.object(
        GOALoginView,
        "verify_credentials",
        return_value=CheckResult(False, "GOA is not available.", reachable=False),
    )
    def test_post_unreachable_keeps_existing(self, mock_method):
        """An unavailable service must not overwrite a saved account."""
        GOALogin.objects.create(user=self.user, username="old", password="old")
        response = self.client.post(self.url, {"username": "new", "password": "new"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing was saved")
        login = GOALogin.objects.get(user=self.user)
        self.assertEqual((login.username, login.password), ("old", "old"))

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
