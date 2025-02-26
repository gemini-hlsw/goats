from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from goats_tom.models import ProgramKey
from goats_tom.tests.factories import (
    ProgramKeyFactory,
    UserFactory,
    UserKeyFactory,
)


@pytest.mark.django_db()
class TestKeyModels:
    def test_key_activation(self):
        # Test activating a key.
        user_key = UserKeyFactory()
        assert not user_key.is_active
        user_key.activate()
        assert user_key.is_active

    def test_key_deactivation(self):
        # Test deactivating a key.
        user_key = UserKeyFactory(is_active=True)
        assert user_key.is_active
        user_key.deactivate()
        assert not user_key.is_active

    def test_unique_active_user_key_per_email_per_site(self):
        # Test that only one active UserKey is allowed per user and email.
        user = UserFactory()
        email = f"{user.username}@example.com"

        # Create two UserKeys with the same user and email.
        key1 = UserKeyFactory(user=user, email=email, site="GN", is_active=False)
        key2 = UserKeyFactory(user=user, email=email, site="GN", is_active=True)

        # Activate the second key, which should deactivate the first one.
        key2.activate()
        key2.refresh_from_db()
        key1.refresh_from_db()

        # Verify that only one key is active.
        assert key2.is_active
        assert not key1.is_active

    def test_multiple_inactive_keys_allowed(self):
        # Test that a user can have multiple inactive keys for the same
        # email/program.
        user = UserFactory()
        email = f"{user.username}@example.com"
        program_id = "GN-2024A-Q-1"
        UserKeyFactory(user=user, email=email, is_active=False)
        UserKeyFactory(user=user, email=email, is_active=False)
        ProgramKeyFactory(user=user, program_id=program_id)

    def test_activating_key_deactivates_others(self):
        # Test activating one key deactivates others for the same user and
        # site.
        user = UserFactory()
        keys = [UserKeyFactory(user=user, site="GS", is_active=False) for _ in range(3)]
        keys.append(UserKeyFactory(user=user, site="GN", is_active=True))

        keys[0].activate()
        # Refresh the other keys to get the updated state from the database.
        keys[1].refresh_from_db()
        keys[2].refresh_from_db()
        keys[3].refresh_from_db()
        assert keys[0].is_active
        assert not keys[1].is_active
        assert not keys[2].is_active
        assert keys[3].is_active

        keys[1].activate()
        # Refresh keys[0] and keys[2] again.
        keys[0].refresh_from_db()
        keys[2].refresh_from_db()
        keys[3].refresh_from_db()
        assert not keys[0].is_active
        assert keys[1].is_active
        assert not keys[2].is_active
        assert keys[3].is_active

    def test_invalid_program_id_raises_error(self):
        # Test that creating a ProgramKey with an invalid program ID raises
        # ValidationError.
        user = UserFactory()
        invalid_program_ids = ["Invalid-Id", "GN-2023A-QQ-A", "GQ-2023A-QQ-10"]

        for program_id in invalid_program_ids:
            program_key = ProgramKeyFactory(user=user, program_id=program_id)
            with pytest.raises(ValidationError):
                program_key.full_clean()

    def test_valid_program_id_passes_validation(self):
        """Test that valid program_ids pass without raising ValidationError."""
        user = UserFactory()
        valid_program_ids = ["GN-2023A-Q-1", "GS-2023B-DD-2"]

        for program_id in valid_program_ids:
            ProgramKeyFactory(user=user, program_id=program_id)

    def test_program_key_uniqueness(self):
        """Test that only one ProgramKey per program_id per site is allowed."""
        user = UserFactory()
        program_id = "GS-2023B-Q-101"

        ProgramKeyFactory(user=user, program_id=program_id, site="GS")
        ProgramKeyFactory(user=user, program_id=program_id, site="GS")

        assert ProgramKey.objects.filter(program_id=program_id, site="GS").count() == 1
