# test_models.py
import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from goats_tom.models import DRAGONSFile
from goats_tom.tests.factories import (
    BaseRecipeFactory,
    DataProductFactory,
    DownloadFactory,
    DRAGONSFileFactory,
    DRAGONSRecipeFactory,
    DRAGONSReduceFactory,
    DRAGONSRunFactory,
    GOALoginFactory,
    ProgramKeyFactory,
    ReducedDatumFactory,
    UserKeyFactory,
    RecipesModuleFactory,
    UserFactory,
    GOALoginFactory,
    AstroDatalabLoginFactory
)



@pytest.mark.django_db()
def test_task_progress_factory():
    # Test the TaskProgress factory.
    task = DownloadFactory.create()

    assert task.unique_id is not None
    assert task.status == "running"
    assert not task.done
    assert task.start_time <= timezone.now()
    assert task.end_time is None
    assert task.user is not None

    # Test the finish method.
    task.finish(message="Test error", error=True)
    assert task.status == "Failed"
    assert task.message == "Test error"
    task.done = True
    assert task.total_time != "N/A"


@pytest.mark.django_db()
class TestDataProductFactory:
    def test_create_dataproduct(self):
        # Test creating a simple DataProduct without any overrides.
        data_product = DataProductFactory()
        assert data_product.pk is not None

    def test_dataproduct_with_overrides(self):
        # Test creating a DataProduct with some field overrides.
        custom_product_id = "custom_id"
        data_product = DataProductFactory(product_id=custom_product_id)
        assert data_product.product_id == custom_product_id

    def test_dataproduct_validation(self):
        # Test that creating a DataProduct with invalid data raises a
        # ValidationError.
        with pytest.raises(ValidationError):
            invalid_data_product = DataProductFactory(data_product_type="invalid_type")
            invalid_data_product.full_clean()


@pytest.mark.django_db()
class TestReducedDatumFactory:
    def test_create_reduceddatum(self):
        # Test creating a simple ReducedDatum without any overrides.
        reduced_datum = ReducedDatumFactory()
        assert reduced_datum.pk is not None

    def test_reduceddatum_with_overrides(self):
        # Test creating a ReducedDatum with some field overrides.
        custom_value = {"magnitude": 20.0, "filter": "g", "error": 0.01}
        reduced_datum = ReducedDatumFactory(value=custom_value)
        assert reduced_datum.value == custom_value

    def test_reduceddatum_validation(self):
        # Test that creating a ReducedDatum with invalid data raises a
        # ValidationError.
        with pytest.raises(ValidationError):
            invalid_reduced_datum = ReducedDatumFactory(data_type="invalid_type")
            invalid_reduced_datum.full_clean()


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


@pytest.mark.django_db()
class TestDRAGONSRunFactory:
    def test_create_dragonsrun(self):
        # Test creating a simple DRAGONSRun without any overrides.
        dragons_run = DRAGONSRunFactory()
        assert dragons_run.pk is not None
        assert dragons_run.output_directory is not None
        assert dragons_run.run_id != ""
        print(dragons_run.run_id)

    def test_dragonsrun_with_overrides(self):
        # Test creating a DRAGONSRun with some field overrides.
        custom_run_id = "custom_run_id"
        dragons_run = DRAGONSRunFactory(run_id=custom_run_id)
        assert dragons_run.run_id == custom_run_id


# @pytest.mark.django_db()
# class TestDataProductMetadataFactory:
#     """Class to test `DataProductMetadataFactory`."""

#     def test_factory_creation(self):
#         """Test that the factory creates a valid metadata instance."""
#         metadata = DataProductMetadataFactory()
#         assert isinstance(
#             metadata, DataProductMetadata,
#         ), "Factory should create a DataProductMetadata instance."

#     def test_factory_with_specific_values(self):
#         """Test factory creation with specific values."""
#         data_product = DataProductFactory()
#         metadata = DataProductMetadataFactory(
#             data_product=data_product,
#             file_type="BIAS",
#             group_id="group_1",
#             exposure_time=30.0,
#             object_name="Test Object",
#             central_wavelength=500.0,
#             wavelength_band="VIS",
#             observation_date="2023-01-01",
#             roi_setting="Full Frame",
#         )
#         assert metadata.data_product == data_product
#         assert metadata.file_type == "BIAS"
#         assert metadata.group_id == "group_1"
#         assert metadata.exposure_time == 30.0
#         assert metadata.object_name == "Test Object"
#         assert metadata.central_wavelength == 500.0
#         assert metadata.wavelength_band == "VIS"
#         assert metadata.observation_date == "2023-01-01"
#         assert metadata.roi_setting == "Full Frame"


@pytest.mark.django_db()
class TestDRAGONSFileFactory:
    """Class to test `DRAGONSFileFactory`."""

    def test_factory_creation(self):
        """Test that the factory creates a valid DRAGONSFile instance."""
        dragons_file = DRAGONSFileFactory()
        assert isinstance(
            dragons_file, DRAGONSFile,
        ), "Factory should create a DRAGONSFile instance."

    def test_factory_with_specific_values(self):
        """Test factory creation with specific values."""
        dragons_run = DRAGONSRunFactory()
        data_product = DataProductFactory()
        dragons_file = DRAGONSFileFactory(
            dragons_run=dragons_run, data_product=data_product,
        )
        assert dragons_file.dragons_run == dragons_run
        assert dragons_file.data_product == data_product


@pytest.mark.django_db()
class TestDRAGONSReduceFactory:
    def test_initial_status(self):
        """Test the initial status of a newly created DRAGONSReduce instance."""
        reduction = DRAGONSReduceFactory()
        assert reduction.status == "created", "Initial status should be 'created'."
        assert (
            reduction.end_time is None
        ), "end_time should be None when status is 'created'."


@pytest.mark.django_db()
class TestBaseRecipeFactory:
    """Class to test the BaseRecipeFactory."""

    def test_factory_with_specific_values(self):
        """Test that the factory correctly applies passed values."""
        recipes_module = RecipesModuleFactory(version="32.2.0")
        recipe = BaseRecipeFactory(name="Test Recipe", recipes_module=recipes_module,
        )
        assert recipe.name == "Test Recipe", "Factory should use the specified name."
        assert recipe.version == "32.2.0", "Factory should use the specified version."


@pytest.mark.django_db()
class TestDRAGONSRecipeFactory:
    """Class to test the DRAGONSRecipeFactory."""

    def test_factory_with_specific_values(self):
        """Test that the factory correctly applies passed values."""
        base_recipe = BaseRecipeFactory()
        dragons_run = DRAGONSRunFactory()
        custom_function_definition = "def custom_processing(): return 'processed'"

        dragons_recipe = DRAGONSRecipeFactory(
            recipe=base_recipe,
            dragons_run=dragons_run,
            function_definition=custom_function_definition,
        )

        assert (
            dragons_recipe.recipe == base_recipe
        ), "Factory should link to the specified BaseRecipe."
        assert (
            dragons_recipe.dragons_run == dragons_run
        ), "Factory should link to the specified DRAGONSRun."
        assert (
            dragons_recipe.function_definition == custom_function_definition
        ), "Factory should use the specified function definition."
        assert (
            dragons_recipe.function_definition is not None
        ), "Function definition should not be None when explicitly set."

    def test_factory_default_function_definition(self):
        """Test that the factory correctly applies default values."""
        dragons_recipe = DRAGONSRecipeFactory(function_definition=None)
        assert (
            dragons_recipe.function_definition is None
        ), "Function definition should be None by default."


class TestGOALogin(TestCase):
    """Tests for the BaseLoginFactory."""

    def setUp(self) -> None:
        """Create a user for all tests in this class."""
        self.user = UserFactory()

    def test_create_login(self) -> None:
        """Test that the factory can create an instance with valid fields for a given
        user.
        """
        login = GOALoginFactory(user=self.user)
        self.assertIsNotNone(login)
        self.assertEqual(login.user, self.user)
        self.assertIsNotNone(login.username)
        self.assertIsNotNone(login.password)


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