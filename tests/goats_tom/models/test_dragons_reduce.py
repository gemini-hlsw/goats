import pytest

from goats_tom.tests.factories import (
    DRAGONSReduceFactory,
)


@pytest.mark.django_db()
class TestDRAGONSReduce:
    """Tests for the `DRAGONSReduce` model."""

    def test_mark_done(self):
        """Test marking a reduction as done sets the correct status and end_time."""
        reduction = DRAGONSReduceFactory(status="running")
        reduction.mark_done()
        assert reduction.status == "done"
        assert reduction.end_time is not None, "Marking done should set end_time."

    def test_mark_error(self):
        """Test marking a reduction as an error sets the correct status and end_time."""
        reduction = DRAGONSReduceFactory(status="running")
        reduction.mark_error()
        assert reduction.status == "error"
        assert reduction.end_time is not None, "Marking error should set end_time."

    def test_mark_running(self):
        """Test changing the status to running."""
        reduction = DRAGONSReduceFactory(status="starting")
        reduction.mark_running()
        assert reduction.status == "running", "Should update status to running."
        assert reduction.end_time is None, "Should not have end time set."

    def test_mark_queued(self):
        """Test changing the status to queued."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_queued()
        assert reduction.status == "queued", "Should update status to queued."
        assert reduction.end_time is None, "Should not have end time set."

    def test_mark_initializing(self):
        """Test changing the status to initializing."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_initializing()
        assert (
            reduction.status == "initializing"
        ), "Should update status to initializing"
        assert reduction.end_time is None, "Should not have end time set."
        assert reduction.start_time is not None, "Should have start time set."

    def test_mark_canceled(self):
        """Test changing the status to canceled."""
        reduction = DRAGONSReduceFactory()
        reduction.mark_canceled()
        assert reduction.status == "canceled", "Should update status to canceled"
        assert reduction.end_time is not None, "Should have end time set."
