from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from goats_tom.tests.factories import TNSLoginFactory, UserFactory



class TestTNSLogin(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_related_name(self) -> None:
        """Test the related name."""
        login = TNSLoginFactory(user=self.user)
        self.assertEqual(self.user.tnslogin, login)

    def test_blank_token_raises_error(self):
        with self.assertRaises(ValidationError):
            login = TNSLoginFactory(user=self.user, token="")
            login.full_clean()

    def test_cannot_assign_same_user_twice(self) -> None:
        # First creation succeeds
        TNSLoginFactory(user=self.user)

        # Second creation with same user should fail
        with self.assertRaises(IntegrityError):
            TNSLoginFactory(user=self.user)
