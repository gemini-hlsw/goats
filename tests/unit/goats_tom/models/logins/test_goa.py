from django.test import TestCase
from goats_tom.tests.factories import UserFactory, GOALoginFactory
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from goats_tom.models import GOALogin

class TestGOALogin(TestCase):
    """Tests for the BaseLoginFactory."""

    def setUp(self) -> None:
        """Create a user for all tests in this class."""
        self.user = UserFactory()

    def test_related_name(self) -> None:
        """Test the related name."""
        login = GOALoginFactory(user=self.user)
        self.assertEqual(self.user.goalogin, login)

    def test_blank_username_raises_error(self):
        with self.assertRaises(ValidationError):
            login = GOALoginFactory(user=self.user, username="")
            login.full_clean()

    def test_cannot_assign_same_user_twice(self) -> None:
        # First creation succeeds
        GOALoginFactory(user=self.user)

        # Second creation with same user should fail
        with self.assertRaises(IntegrityError):
            GOALoginFactory(user=self.user)
