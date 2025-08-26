import pytest

from goats_tom.tests.factories import (
    DRAGONSReduceFactory,
)


@pytest.mark.django_db()
class TestDRAGONSReduceFactory:
    def test_initial_status(self):
        """Test the initial status of a newly created DRAGONSReduce instance."""
        reduction = DRAGONSReduceFactory()
        assert reduction.status == "created", "Initial status should be 'created'."
        assert (
            reduction.end_time is None
        ), "end_time should be None when status is 'created'."
