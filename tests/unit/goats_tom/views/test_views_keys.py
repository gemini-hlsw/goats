import pytest
from django.test import Client, TestCase
from django.urls import reverse
from goats_tom.models import ProgramKey, UserKey
from goats_tom.tests.factories import (
    ProgramKeyFactory,
    UserFactory,
    UserKeyFactory,
)


@pytest.mark.django_db()
class TestActivateUserKeyView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = UserFactory()
        cls.other_user = UserFactory()
        cls.user_key = UserKeyFactory(user=cls.user)
        cls.url = reverse("activate-user-key", args=[cls.user.pk, cls.user_key.pk])

    def test_activate_user_key_success(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.user_key.refresh_from_db()
        self.assertTrue(self.user_key.is_active)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

    def test_activate_user_key_unauthorized(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.user_key.refresh_from_db()
        self.assertFalse(self.user_key.is_active)
        self.assertRedirects(
            response, reverse("manage-keys", args=[self.other_user.pk]),
        )


@pytest.mark.django_db()
class TestCreateKeyView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = UserFactory()
        cls.other_user = UserFactory()
        cls.user_key_url = reverse("create-user-key", args=[cls.user.pk])
        cls.program_key_url = reverse("create-program-key", args=[cls.user.pk])
        cls.user_key_data = {
            "user_key-email": "test@example.com",
            "user_key-site": "GS",
            "user_key-password": "pass",
        }
        cls.program_key_data = {
            "program_key-program_id": "GS-2023B-Q-101",
            "program_key-site": "GN",
            "program_key-password": "pass",
        }

    def test_create_user_key_success(self):
        self.client.force_login(self.user)
        response = self.client.post(self.user_key_url, data=self.user_key_data)
        self.assertEqual(UserKey.objects.count(), 1)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

    def test_create_user_key_unauthorized(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            self.user_key_url,
            data=self.user_key_data,
        )
        self.assertEqual(UserKey.objects.count(), 0)
        self.assertRedirects(
            response, reverse("manage-keys", args=[self.other_user.pk]),
        )

    def test_create_program_key_success(self):
        """Test successful creation of a program key."""
        self.client.force_login(self.user)
        response = self.client.post(self.program_key_url, data=self.program_key_data)
        self.assertEqual(ProgramKey.objects.count(), 1)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

    def test_replace_existing_program_key(self):
        """Test that an existing program key is replaced by a new one with the
        same program_id and site.
        """
        # Create initial program key
        ProgramKeyFactory(user=self.user, program_id="GS-2023B-Q-101", site="GN")

        # Attempt to create a new key with the same program_id and site
        self.client.force_login(self.user)
        response = self.client.post(self.program_key_url, data=self.program_key_data)
        self.assertEqual(ProgramKey.objects.count(), 1)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

        # Ensure the new key replaced the old one
        new_key = ProgramKey.objects.first()
        self.assertEqual(new_key.program_id, "GS-2023B-Q-101")
        self.assertEqual(new_key.site, "GN")

    def test_create_program_key_unauthorized(self):
        """Test unauthorized attempt to create a program key."""
        other_user = UserFactory()
        self.client.force_login(other_user)
        response = self.client.post(self.program_key_url, data=self.program_key_data)
        self.assertEqual(ProgramKey.objects.count(), 0)
        self.assertRedirects(response, reverse("manage-keys", args=[other_user.pk]))


@pytest.mark.django_db()
class TestDeleteKeyView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = UserFactory()
        cls.other_user = UserFactory()
        cls.user_key = UserKeyFactory(user=cls.user)
        cls.program_key = ProgramKeyFactory(user=cls.user)
        cls.user_key_url = reverse(
            "delete-user-key", args=[cls.user.pk, cls.user_key.pk],
        )
        cls.program_key_url = reverse(
            "delete-program-key", args=[cls.user.pk, cls.user_key.pk],
        )

    def test_delete_user_key_success(self):
        self.client.force_login(self.user)
        self.assertEqual(UserKey.objects.count(), 1)
        response = self.client.get(self.user_key_url)
        self.assertEqual(UserKey.objects.count(), 0)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

    def test_delete_user_key_unauthorized(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.user_key_url)
        self.assertEqual(UserKey.objects.count(), 1)
        self.assertRedirects(
            response, reverse("manage-keys", args=[self.other_user.pk]),
        )

    def test_delete_program_key_success(self):
        self.client.force_login(self.user)
        self.assertEqual(ProgramKey.objects.count(), 1)
        response = self.client.get(self.program_key_url)
        self.assertEqual(ProgramKey.objects.count(), 0)
        self.assertRedirects(response, reverse("manage-keys", args=[self.user.pk]))

    def test_delete_program_key_unauthorized(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.program_key_url)
        self.assertEqual(ProgramKey.objects.count(), 1)
        self.assertRedirects(
            response, reverse("manage-keys", args=[self.other_user.pk]),
        )


@pytest.mark.django_db()
class TestManageKeysView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.url = reverse("manage-keys", args=[self.user.pk])

    def test_manage_keys_view(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("user_key_form", response.context)
        self.assertIn("program_key_form", response.context)
        self.assertIn("user_keys", response.context)
        self.assertIn("program_keys", response.context)

    def test_manage_keys_view_unauthorized(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Redirects to login page

