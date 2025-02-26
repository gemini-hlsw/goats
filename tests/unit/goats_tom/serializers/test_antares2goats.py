from goats_tom.serializers import Antares2GoatsSerializer
from rest_framework.exceptions import ValidationError
import pytest

class TestAntares2GoatsSerializer:
    def test_validate_success_with_esquery(self):
        """Test serializer with valid esquery provided."""
        serializer = Antares2GoatsSerializer(data={'esquery': {"key": "value"}})
        assert serializer.is_valid()
        assert serializer.validated_data == {'esquery': {"key": "value"}}

    def test_validate_success_with_locusid(self):
        """Test serializer with valid locusid provided."""
        serializer = Antares2GoatsSerializer(data={'locusid': 'some_id'})
        assert serializer.is_valid()
        assert serializer.validated_data == {'locusid': 'some_id'}

    def test_validate_failure_with_neither_field(self):
        """Test serializer raises ValidationError when neither field is provided."""
        serializer = Antares2GoatsSerializer(data={})
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert "Either 'esquery' or 'locusid' must be provided." in str(excinfo.value)

    def test_validate_failure_with_both_fields(self):
        """Test serializer raises ValidationError when both fields are provided."""
        serializer = Antares2GoatsSerializer(data={'esquery': {"key": "value"}, 'locusid': 'some_id'})
        with pytest.raises(ValidationError) as excinfo:
            serializer.is_valid(raise_exception=True)
        assert "Only one of 'esquery' or 'locusid' should be provided." in str(excinfo.value)