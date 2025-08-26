import pytest
from django.core.exceptions import ValidationError

from goats_tom.tests.factories import (
    DataProductFactory,
)


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
