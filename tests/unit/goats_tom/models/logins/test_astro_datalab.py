from django.test import TestCase
from goats_tom.tests.factories import UserFactory, AstroDatalabLoginFactory
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError


class TestAstroDataLab(TestCase):
    """Tests for the BaseLoginFactory."""

    def setUp(self) -> None:
        """Create a user for all tests in this class."""
        self.user = UserFactory()

    def test_related_name(self) -> None:
        """Test the related name."""
        login = AstroDatalabLoginFactory(user=self.user)
        self.assertEqual(self.user.astrodatalablogin, login)

    def test_blank_username_raises_error(self):
        with self.assertRaises(ValidationError):
            login = AstroDatalabLoginFactory(user=self.user, username="")
            login.full_clean()

    def test_cannot_assign_same_user_twice(self) -> None:
        # First creation succeeds
        AstroDatalabLoginFactory(user=self.user)

        # Second creation with same user should fail
        with self.assertRaises(IntegrityError):
            AstroDatalabLoginFactory(user=self.user)
