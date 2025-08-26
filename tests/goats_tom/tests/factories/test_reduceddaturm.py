# test_models.py
import pytest
from django.core.exceptions import ValidationError

from goats_tom.tests.factories import (
    ReducedDatumFactory,
)


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
