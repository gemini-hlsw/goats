from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token


class TestUserGenerateTokenView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.superuser = User.objects.create_superuser(
            "superuser", "super@example.com", "password",
        )
        cls.normal_user = User.objects.create_user(
            "normaluser", "normal@example.com", "password",
        )
        cls.target_user = User.objects.create_user(
            "targetuser", "target@example.com", "password",
        )

    def test_superuser_generates_token(self):
        self.client.login(username="superuser", password="password")
        response = self.client.get(
            reverse("user-generate-token", kwargs={"pk": self.target_user.pk}),
        )
        self.assertEqual(response.status_code, 200)

        # Check if token is created.
        token_exists = Token.objects.filter(user=self.target_user).exists()
        self.assertTrue(token_exists)

        # Verify context contains user and token.
        self.assertIn("user", response.context)
        self.assertIn("token", response.context)
        self.assertEqual(response.context["user"], self.target_user)

    def test_non_superuser_access_denied(self):
        self.client.login(username="normaluser", password="password")
        token_url = reverse("user-generate-token", kwargs={"pk": self.target_user.pk})
        login_url = reverse("login")

        # Construct the expected URL with 'next' parameter
        expected_url = f"{login_url}?next={token_url}"
        response = self.client.get(token_url)

        self.assertRedirects(
            response, expected_url, status_code=302, target_status_code=200,
        )

    def test_user_not_found(self):
        self.client.login(username="superuser", password="password")
        response = self.client.get(reverse("user-generate-token", kwargs={"pk": 999}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("user-list"))

    def tearDown(self):
        self.client.logout()
