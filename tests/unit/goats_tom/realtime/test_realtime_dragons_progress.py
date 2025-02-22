"""Tests for `DRAGONSProgress`."""

from unittest.mock import patch

import pytest
from goats_tom.realtime import DRAGONSProgress
from goats_tom.tests.factories import DRAGONSReduceFactory


@pytest.mark.django_db()
def test_dragons_progress():
    """Tests creating and sending progress updates for DRAGONS recipes."""
    # Create a DRAGONSReduce instance using the factory.
    reduce = DRAGONSReduceFactory()

    with patch.object(DRAGONSProgress, "_send") as mock_send:
        # Test the create_and_send method
        DRAGONSProgress.create_and_send(reduce)

        # Verify that _send was called with the correct parameters.
        mock_send.assert_called_once()
        args, _ = mock_send.call_args

        status, run_id, recipe_id, reduce_id = args

        assert status == reduce.status, f"Status mismatch {status}!={reduce.status}"
        assert run_id == reduce.recipe.dragons_run.id, "Run ID mismatch"
        assert recipe_id == reduce.recipe.id, "Recipe ID mismatch"
        assert reduce_id == reduce.id, "Reduce ID mismatch"
