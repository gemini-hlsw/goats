import pytest
from goats_tom.models import DRAGONSFile
from goats_tom.tests.factories import (
    DataProductFactory,
    DRAGONSFileFactory,
    DRAGONSRunFactory,
)


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
