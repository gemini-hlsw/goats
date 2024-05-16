from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from goats_tom.models import ProgramKey
from goats_tom.tests.factories import (
    DataProductMetadataFactory,
    DownloadFactory,
    DRAGONSFileFactory,
    DRAGONSRecipeFactory,
    DRAGONSRunFactory,
    GOALoginFactory,
    ProgramKeyFactory,
    UserFactory,
    UserKeyFactory,
)
from tom_observations.tests.factories import ObservingRecordFactory


@pytest.mark.django_db
class TestGOALoginModel(TestCase):
    def setUp(self):
        self.goa_login = GOALoginFactory()

    def test_empty_password(self):
        self.goa_login.password = ""
        with pytest.raises(ValidationError):
            self.goa_login.clean()


@pytest.mark.django_db
class TestDownloadModel(TestCase):
    def setUp(self):
        self.task = DownloadFactory()

    def test_immediate_task_completion(self):
        self.task.finish()
        assert self.task.total_time == "0s"

    def test_long_duration_task(self):
        self.task.start_time = timezone.now() - timedelta(
            days=1
        )  # Simulate a long-running task
        self.task.finish()
        assert "1d" in self.task.total_time


@pytest.mark.django_db
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


@pytest.mark.django_db
class TestDRAGONSRun:
    def test_automatic_run_id_generation(self):
        """Test that "run_id" is automatically generated if not provided."""
        dragons_run = DRAGONSRunFactory(run_id="")
        assert dragons_run.run_id != "", "run_id should be automatically generated."

    def test_automatic_output_directory_generation(self):
        """Test that "output_directory" is automatically generated if not
        provided.
        """
        dragons_run = DRAGONSRunFactory(output_directory="")
        assert (
            dragons_run.output_directory != ""
        ), "output_directory should be automatically generated."

    def test_unique_observation_run_id_constraint(self):
        """Test that the unique constraint between "observation_record" and
        "run_id" is enforced.
        """
        observation_record = ObservingRecordFactory(target_id=1)
        run_id = "unique_run_id"
        DRAGONSRunFactory(observation_record=observation_record, run_id=run_id)

        with pytest.raises(ValidationError):
            duplicate_run = DRAGONSRunFactory.build(
                observation_record=observation_record, run_id=run_id
            )
            duplicate_run.full_clean()


@pytest.mark.django_db
class TestDataProductMetadata:
    """Class to test `DataProductMetadata` model."""

    def test_create_metadata(self):
        """Test creating a metadata instance."""
        metadata = DataProductMetadataFactory()
        assert metadata.pk is not None, "Metadata should be created successfully."

    def test_null_fields(self):
        """Test metadata creation with null fields."""
        metadata = DataProductMetadataFactory(
            file_type=None,
            group_id=None,
            exposure_time=None,
            object_name=None,
            central_wavelength=None,
            wavelength_band=None,
            observation_date=None,
            roi_setting=None,
        )
        assert (
            metadata.pk is not None
        ), "Metadata with null fields should be created successfully."

    def test_empty_strings(self):
        """Test metadata creation with empty strings."""
        metadata = DataProductMetadataFactory(
            file_type="",
            group_id="",
            object_name="",
            wavelength_band="",
            roi_setting="",
        )
        assert (
            metadata.pk is not None
        ), "Metadata with empty strings should be created successfully."

    def test_invalid_exposure_time(self):
        """Test metadata creation with negative exposure time."""
        with pytest.raises(ValidationError):
            metadata = DataProductMetadataFactory.build(exposure_time=-1)
            metadata.full_clean()

    def test_invalid_central_wavelength(self):
        """Test metadata creation with negative central wavelength."""
        with pytest.raises(ValidationError):
            metadata = DataProductMetadataFactory.build(central_wavelength=-1)
            metadata.full_clean()

    def test_string_representation(self):
        """Test the string representation of the metadata."""
        metadata = DataProductMetadataFactory()
        assert str(metadata) == f"Metadata for {metadata.data_product.product_id}"


@pytest.mark.django_db
class TestDRAGONSFile:
    """Class to test `DRAGONSFile` model."""

    def test_create_file(self):
        """Test creating a DRAGONSFile instance."""
        dragons_file = DRAGONSFileFactory()
        assert (
            dragons_file.pk is not None
        ), "DRAGONSFile should be created successfully."

    def test_unique_constraint(self):
        """Test the unique constraint between dragons_run and data_product."""
        dragons_file = DRAGONSFileFactory()
        with pytest.raises(ValidationError):
            duplicate_file = DRAGONSFileFactory.build(
                dragons_run=dragons_file.dragons_run,
                data_product=dragons_file.data_product,
            )
            duplicate_file.full_clean()

    def test_file_path(self):
        """Test the get_file_path method."""
        dragons_file = DRAGONSFileFactory()
        assert dragons_file.get_file_path() == dragons_file.data_product.data.path

    def test_file_type(self):
        """Test the get_file_type method."""
        dragons_file = DRAGONSFileFactory()
        assert (
            dragons_file.get_file_type() == dragons_file.data_product.metadata.file_type
        )


@pytest.mark.django_db
class TestDRAGONSRecipe:
    """Class to test `DRAGONSRecipe` model."""

    def test_create_recipe(self):
        """Test creating a DRAGONSRecipe instance."""
        recipe = DRAGONSRecipeFactory()
        assert recipe.pk is not None, "DRAGONSRecipe should be created successfully."

    def test_unique_constraint(self):
        """Test the unique constraint between dragons_run, file_type, and name."""
        recipe = DRAGONSRecipeFactory()
        with pytest.raises(ValidationError):
            duplicate_recipe = DRAGONSRecipeFactory.build(
                dragons_run=recipe.dragons_run,
                file_type=recipe.file_type,
                name=recipe.name,
            )
            duplicate_recipe.full_clean()

    def test_short_name(self):
        """Test the short_name property."""
        name_with_short = "full_name::short_name"
        recipe = DRAGONSRecipeFactory(name=name_with_short)
        assert recipe.short_name == "short_name"

        name_without_short = "full_name"
        recipe = DRAGONSRecipeFactory(name=name_without_short)
        assert recipe.short_name is None
