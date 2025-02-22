from goats_tom.serializers import (
    DRAGONSRunSerializer,
)
from goats_tom.tests.factories import (
    DRAGONSRunFactory,
)
from django.forms.models import model_to_dict
from rest_framework.test import APITestCase


class TestDRAGONSRunSerializer(APITestCase):
    """Test class for `DRAGONSRunSerializer`."""

    def test_valid_data(self):
        """Test `DRAGONSRunSerializer` with valid data."""
        dragons_run = DRAGONSRunFactory()
        serializer = DRAGONSRunSerializer(dragons_run)

        self.assertEqual(
            serializer.data["observation_id"],
            dragons_run.observation_record.observation_id,
        )
        self.assertEqual(serializer.data["run_id"], dragons_run.run_id)
        self.assertEqual(
            serializer.data["config_filename"], dragons_run.config_filename,
        )
        self.assertEqual(
            serializer.data["output_directory"], dragons_run.output_directory,
        )
        self.assertEqual(
            serializer.data["cal_manager_filename"], dragons_run.cal_manager_filename,
        )
        self.assertEqual(serializer.data["log_filename"], dragons_run.log_filename)

    def test_invalid_data(self):
        """Test `DRAGONSRunSerializer` with invalid data."""
        invalid_data = {"output_directory": None}
        serializer = DRAGONSRunSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())

    def test_run_id_sanitization(self):
        """Test the sanitization of `run_id` with various edge cases."""

        test_cases = [
            ("NormalID2023", "normalid2023"),
            ("123_456-789", "123_456-789"),
            ("Test@ID#2023$", "testid2023"),
            ("Run ID with spaces", "run_id_with_spaces"),
            ("ID_with!special*chars", "id_withspecialchars"),
            ("ID-with.dots/and,commas", "id-withdotsandcommas")
        ]

        # Create a default instance with all necessary attributes set
        dragons_run = DRAGONSRunFactory()

        for input_id, expected in test_cases:
            with self.subTest(input_id=input_id):
                # Manually set the run_id for each test case
                dragons_run.run_id = input_id

                # Serialize to dictionary and modify the run_id
                dragons_run_data = model_to_dict(dragons_run)
                dragons_run_data['run_id'] = input_id  # Ensure run_id is updated for test

                serializer = DRAGONSRunSerializer(data=dragons_run_data)
                if serializer.is_valid():
                    self.assertEqual(serializer.validated_data['run_id'], expected)
                else:
                    self.fail(f"Serializer with run_id '{input_id}' should be valid but errors were: {serializer.errors}")
