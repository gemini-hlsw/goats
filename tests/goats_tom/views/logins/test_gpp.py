from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from goats_tom.service_checks import CheckResult

from goats_tom.models import GPPLogin
from goats_tom.views import GPPLoginView


class TestGPPLoginView(TestCase):
    """Tests for the GPPLoginView, which inherits from BaseLoginView."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="secret")
        self.client.login(username="testuser", password="secret")
        self.url = reverse("user-gpp-login", kwargs={"pk": self.user.pk})

    def test_get_request_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/login_form.html")
        self.assertContains(response, "GPP")
        self.assertContains(response, "token")

    @patch.object(GPPLoginView, "verify_credentials", return_value=CheckResult(True, "ok"))
    def test_post_valid_credentials(self, mock_method):
        form_data = {"token": "gpp_token"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(
            response, reverse("user-update", kwargs={"pk": self.user.pk})
        )
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any("GPP login information verified" in str(msg) for msg in messages_list)
        )

        login_obj = GPPLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.token, "gpp_token")

    @patch.object(GPPLoginView, "verify_credentials", return_value=CheckResult(False, "rejected"))
    def test_post_invalid_credentials(self, mock_method):
        """
        Invalid credentials -> failure message, and nothing is written.
        """
        form_data = {"token": "bad_token"}
        response = self.client.post(self.url, form_data)

        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any(
                "Could not verify GPP credentials" in str(msg)
                for msg in messages_list
            )
        )
        self.assertFalse(GPPLogin.objects.filter(user=self.user).exists())

    @patch.object(GPPLoginView, "verify_credentials", return_value=CheckResult(False, "rejected"))
    def test_post_invalid_credentials_keeps_existing(self, mock_method):
        """
        A failed check leaves previously saved credentials untouched.
        """
        GPPLogin.objects.create(user=self.user, token="good_token")

        self.client.post(self.url, {"token": "typo_token"})

        self.assertEqual(GPPLogin.objects.get(user=self.user).token, "good_token")

    def test_post_form_invalid(self):
        form_data = {"token": ""}
        response = self.client.post(self.url, form_data)

        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any(
                "Failed to save GPP login information" in str(msg)
                for msg in messages_list
            )
        )
        self.assertFalse(GPPLogin.objects.filter(user=self.user).exists())

    @patch("goats_tom.views.logins.gpp.check_gpp")
    def test_verify_credentials_uses_check(self, mock_check):
        mock_check.return_value = CheckResult(False, "rejected")

        result = GPPLoginView().verify_credentials(token="bad_token")

        assert result == CheckResult(False, "rejected")
        mock_check.assert_called_once_with("bad_token")

    def test_inconclusive_checks_never_save_or_replace(self):
        """A timeout or ambiguous API failure cannot replace a working token."""
        results = [
            CheckResult(False, "Cannot connect", reachable=False),
            CheckResult(False, "Check incomplete", verified=False),
        ]
        for result in results:
            for existing in (False, True):
                with self.subTest(result=result, existing=existing):
                    GPPLogin.objects.filter(user=self.user).delete()
                    if existing:
                        GPPLogin.objects.create(user=self.user, token="saved-token")
                    with patch.object(GPPLoginView, "verify_credentials", return_value=result):
                        response = self.client.post(self.url, {"token": "replacement"})
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, "Nothing was saved")
                    self.assertNotContains(response, "GPP rejected them")
                    if existing:
                        self.assertEqual(GPPLogin.objects.get(user=self.user).token, "saved-token")
                    else:
                        self.assertFalse(GPPLogin.objects.filter(user=self.user).exists())
