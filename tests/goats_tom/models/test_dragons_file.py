from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from goats_tom.tests.factories import (
    DataProductFactory,
    DRAGONSFileFactory,
)


@pytest.fixture()
def gmos_test_file():
    file_path = Path(__file__).parent.parent.parent / "data" / "gmos_bias.fits"
    return file_path


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
