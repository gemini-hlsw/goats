import pytest

from goats_tom.tests.factories import (
    DRAGONSRunFactory,
)


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
