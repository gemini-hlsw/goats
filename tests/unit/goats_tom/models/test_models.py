from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone
from goats_tom.models import BaseRecipe, ProgramKey
from goats_tom.tests.factories import (
    BaseRecipeFactory,
    DownloadFactory,
    DRAGONSFileFactory,
    DRAGONSRecipeFactory,
    DRAGONSReduceFactory,
    DRAGONSRunFactory,
    ProgramKeyFactory,
    UserFactory,
    UserKeyFactory,
    DataProductFactory,
    RecipesModuleFactory
)
from tom_observations.tests.factories import ObservingRecordFactory

@pytest.fixture()
def gmos_test_file():
    file_path = Path(__file__).parent.parent.parent / "data" / "gmos_bias.fits"
    return file_path


@pytest.mark.django_db()
class TestDownloadModel(TestCase):
    def setUp(self):
        self.task = DownloadFactory()

    def test_immediate_task_completion(self):
        self.task.finish()
        assert self.task.total_time == "0s"

    def test_long_duration_task(self):
        self.task.start_time = timezone.now() - timedelta(
            days=1,
        )  # Simulate a long-running task
        self.task.finish()
        assert "1d" in self.task.total_time


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


@pytest.mark.django_db()
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
                observation_record=observation_record, run_id=run_id,
            )
            duplicate_run.full_clean()


@pytest.mark.django_db
class RecipesModuleTests(TestCase):
    def test_create_recipes_module(self):
        """Ensure that the RecipesModule can be created with valid attributes using the
        factory.

        """
        module = RecipesModuleFactory()
        self.assertIsNotNone(
            module.pk, 
            "Failed to save the RecipesModule instance to the database."
        )

    def test_unique_constraints(self):
        """Verify that the unique constraints on `name`, `version`, and `instrument`
        are enforced by the database.

        """
        # Create an initial module with specific details.
        module1 = RecipesModuleFactory(name="Astro", version="1.0.0", 
                                       instrument="Telescope")
        module1.save()

        # Attempt to create another module with the same details.
        module2 = RecipesModuleFactory.build(
            name="Astro", version="1.0.0", instrument="Telescope")
        with self.assertRaises(
            IntegrityError, 
            msg="Database failed to enforce uniqueness."):
            module2.save()
            
            
@pytest.mark.django_db()
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

    def test_list_primitives_and_docstrings(self, gmos_test_file):
        """Test listing primitives and docstrings of the associated file type."""
        data_product = DataProductFactory(data__from_path=gmos_test_file)
        dragons_file = DRAGONSFileFactory(data_product=data_product)
        help_return = dragons_file.list_primitives_and_docstrings()
        assert isinstance(help_return, dict), "Expected the return value to be a dictionary."
        assert help_return, "The dictionary should not be empty."
        assert "ADUToElectrons" in help_return, "The dictionary should contain the 'ADUToElectrons' key."
        assert "docstring" in help_return["ADUToElectrons"], "The 'ADUToElectrons' entry should contain a 'docstring' key."

@pytest.mark.django_db()
class TestDRAGONSReduce:
    """Tests for the `DRAGONSReduce` model."""

    def test_mark_done(self):
        """Test marking a reduction as done sets the correct status and end_time."""
        reduction = DRAGONSReduceFactory(status="running")
        reduction.mark_done()
        assert reduction.status == "done"
        assert reduction.end_time is not None, "Marking done should set end_time."

    def test_mark_error(self):
        """Test marking a reduction as an error sets the correct status and end_time."""
        reduction = DRAGONSReduceFactory(status="running")
        reduction.mark_error()
        assert reduction.status == "error"
        assert reduction.end_time is not None, "Marking error should set end_time."

    def test_mark_running(self):
        """Test changing the status to running."""
        reduction = DRAGONSReduceFactory(status="starting")
        reduction.mark_running()
        assert reduction.status == "running", "Should update status to running."
        assert reduction.end_time is None, "Should not have end time set."

    def test_mark_queued(self):
        """Test changing the status to queued."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_queued()
        assert reduction.status == "queued", "Should update status to queued."
        assert reduction.end_time is None, "Should not have end time set."

    def test_mark_initializing(self):
        """Test changing the status to initializing."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_initializing()
        assert (
            reduction.status == "initializing"
        ), "Should update status to initializing"
        assert reduction.end_time is None, "Should not have end time set."
        assert reduction.start_time is not None, "Should have start time set."

    def test_mark_canceled(self):
        """Test changing the status to canceled."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_canceled()
        assert reduction.status == "canceled", "Should update status to canceled"
        assert reduction.end_time is not None, "Should have end time set."


@pytest.mark.django_db()
class TestBaseRecipe:
    """Tests for the BaseRecipe model."""

    def test_factory_creation(self):
        """Ensure the BaseRecipe factory correctly creates a new instance."""
        base_recipe = BaseRecipeFactory()
        assert (
            base_recipe.pk is not None
        ), "BaseRecipe should be created with a primary key."
        assert isinstance(
            base_recipe, BaseRecipe,
        ), "Factory should create a BaseRecipe instance."

    def test_short_name_extraction(self):
        """Test the extraction of short_name from the name attribute."""
        base_recipe_with_short = BaseRecipeFactory(name="Recipe::ShortName")
        assert (
            base_recipe_with_short.short_name == "ShortName"
        ), "Should correctly extract 'ShortName'."

        base_recipe_without_short = BaseRecipeFactory(name="RecipeWithoutDelimiter")
        assert (
            base_recipe_without_short.short_name == "Unknown"
        ), "Should return 'Unknown' if delimiter '::' is absent."

    def test_unique_constraints(self):
        """Ensure that BaseRecipe respects its unique-together constraint."""
        base_recipe = BaseRecipeFactory()
        with pytest.raises(ValidationError):
            duplicate_recipe = BaseRecipeFactory.build(
                name=base_recipe.name,
            )
            duplicate_recipe.full_clean()

@pytest.mark.django_db()
class TestDRAGONSRecipe:
    """Test suite for the DRAGONSRecipe model."""

    def test_DRAGONSRecipe_creation(self):
        """Verify that a DRAGONSRecipe instance can be created successfully."""
        dragons_recipe = DRAGONSRecipeFactory()
        assert dragons_recipe.pk is not None, "Should create a DRAGONSRecipe instance."

    def test_base_recipe_link(self):
        """Ensure the DRAGONSRecipe links correctly to a BaseRecipe."""
        base_recipe = BaseRecipeFactory()
        dragons_recipe = DRAGONSRecipeFactory(recipe=base_recipe)
        assert (
            dragons_recipe.recipe == base_recipe
        ), "Should link to the correct BaseRecipe."

    def test_dragons_run_link(self):
        """Ensure the DRAGONSRecipe links correctly to a DRAGONSRun."""
        dragons_run = DRAGONSRunFactory()
        dragons_recipe = DRAGONSRecipeFactory(dragons_run=dragons_run)
        assert (
            dragons_recipe.dragons_run == dragons_run
        ), "Should link to the correct DRAGONSRun."

    def test_function_definition_default(self):
        """Check that the function definition defaults to None."""
        dragons_recipe = DRAGONSRecipeFactory()
        assert (
            dragons_recipe.function_definition is None
        ), "Function definition should default to None."

    def test_active_function_definition(self):
        """Test active function definition retrieval logic."""
        base_recipe = BaseRecipeFactory(function_definition="def base_func(): pass")
        modified_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe, function_definition="def modified_func(): pass",
        )
        assert (
            modified_recipe.active_function_definition == "def modified_func(): pass"
        ), "Should return the modified function definition when set."

        unmodified_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe, function_definition=None,
        )
        assert (
            unmodified_recipe.active_function_definition
            == base_recipe.function_definition
        ), "Should fallback to the base recipe's function definition when none is set."

    def test_unique_together_constraint(self):
        """Test that the unique together constraint on recipe and dragons_run is enforced."""
        first_recipe = DRAGONSRecipeFactory(object_name="test")
        with pytest.raises(IntegrityError):
            DRAGONSRecipeFactory(
                recipe=first_recipe.recipe, dragons_run=first_recipe.dragons_run, observation_type=first_recipe.observation_type, object_name=first_recipe.object_name,
                observation_class=first_recipe.observation_class,
            )

    def test_properties(self):
        """Test that model properties return correct values derived from the base recipe."""
        base_recipe = BaseRecipeFactory(name="ComplexRecipe::Simple",
        )
        dragons_recipe = DRAGONSRecipeFactory(recipe=base_recipe)
        assert (
            dragons_recipe.name == "ComplexRecipe::Simple"
        ), "Name should be retrieved from the base recipe."
        assert (
            dragons_recipe.short_name == "Simple"
        ), "Should correctly extract the short name from the base recipe."
