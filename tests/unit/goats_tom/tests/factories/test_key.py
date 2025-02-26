import pytest
from django.test import TestCase
from goats_tom.tests.factories import (
    ProgramKeyFactory,
    UserKeyFactory,
)


@pytest.mark.django_db()
class KeyFactoryTest(TestCase):
    def test_user_key_factory(self):
        user_key = UserKeyFactory()
        self.assertIsNotNone(user_key.id)
        self.assertTrue(user_key.email.endswith("@example.com"))
        self.assertIn(user_key.site, ["GS", "GN"])
        self.assertFalse(user_key.is_active)

    def test_program_key_factory(self):
        program_key = ProgramKeyFactory()
        self.assertIsNotNone(program_key.id)
        self.assertTrue(program_key.program_id.startswith("GN-2024A-Q-"))
        self.assertIn(program_key.site, ["GS", "GN"])
