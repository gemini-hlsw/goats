from django.test import TestCase

from goats_tom.tests.factories import AstroDatalabLoginFactory, UserFactory


class TestAstroDataLab(TestCase):
    """Tests for the BaseLoginFactory."""

    def setUp(self) -> None:
        """Create a user for all tests in this class."""
        self.user = UserFactory()

    def test_create_login(self) -> None:
        """Test that the factory can create an instance with valid fields for a given
        user.
        """
        login = AstroDatalabLoginFactory(user=self.user)
        self.assertIsNotNone(login)
        self.assertEqual(login.user, self.user)
        self.assertIsNotNone(login.username)
        self.assertIsNotNone(login.password)
