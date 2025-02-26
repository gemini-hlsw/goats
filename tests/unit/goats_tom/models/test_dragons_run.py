import pytest
from django.core.exceptions import ValidationError
from goats_tom.tests.factories import (
    DRAGONSRunFactory,
)
from tom_observations.tests.factories import ObservingRecordFactory


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

