from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

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

    @patch.object(GPPLoginView, "perform_login_and_logout", return_value=True)
    def test_post_valid_credentials(self, mock_method):
        form_data = {"token": "gpp_token"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any("GPP login information verified" in str(msg) for msg in messages_list)
        )

        login_obj = GPPLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.token, "gpp_token")

    @patch.object(GPPLoginView, "perform_login_and_logout", return_value=False)
    def test_post_invalid_credentials(self, mock_method):
        form_data = {"token": "bad_token"}
        response = self.client.post(self.url, form_data, follow=True)

        self.assertRedirects(response, reverse("user-list"))
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any(
                "Failed to verify GPP credentials" in str(msg) for msg in messages_list
            )
        )

        login_obj = GPPLogin.objects.get(user=self.user)
        self.assertEqual(login_obj.token, "bad_token")

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

    @patch("goats_tom.views.logins.gpp.GPPClient")
    @patch("goats_tom.views.logins.gpp.async_to_sync")
    def test_perform_login_and_logout_success(self, mock_async_to_sync, mock_client):
        mock_async_to_sync.return_value = lambda: (True, None)

        view = GPPLoginView()
        result = view.perform_login_and_logout(token="valid_token")

        assert result is True
        mock_client.assert_called_once_with(token="valid_token")

    @patch("goats_tom.views.logins.gpp.GPPClient")
    @patch("goats_tom.views.logins.gpp.async_to_sync")
    def test_perform_login_and_logout_unreachable(
        self, mock_async_to_sync, mock_client
    ):
        mock_async_to_sync.return_value = lambda: (False, "unreachable")

        view = GPPLoginView()
        result = view.perform_login_and_logout(token="bad_token")

        assert result is False

    @patch("goats_tom.views.logins.gpp.GPPClient")
    @patch("goats_tom.views.logins.gpp.async_to_sync")
    def test_perform_login_and_logout_raises(self, mock_async_to_sync, mock_client):
        def _raise():
            raise RuntimeError("boom")

        mock_async_to_sync.return_value = _raise

        view = GPPLoginView()
        result = view.perform_login_and_logout(token="erroring_token")

        assert result is False
