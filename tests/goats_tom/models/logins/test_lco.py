from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from goats_tom.tests.factories import LCOLoginFactory, UserFactory



class TestLCOLogin(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_related_name(self) -> None:
        """Test the related name."""
        login = LCOLoginFactory(user=self.user)
        self.assertEqual(self.user.lcologin, login)

    def test_blank_token_raises_error(self):
        with self.assertRaises(ValidationError):
            login = LCOLoginFactory(user=self.user, token="")
            login.full_clean()

    def test_cannot_assign_same_user_twice(self) -> None:
        # First creation succeeds
        LCOLoginFactory(user=self.user)

        # Second creation with same user should fail
        with self.assertRaises(IntegrityError):
            LCOLoginFactory(user=self.user)
