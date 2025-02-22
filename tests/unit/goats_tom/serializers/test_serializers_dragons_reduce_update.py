from goats_tom.serializers import (
    DRAGONSReduceUpdateSerializer,
)
from goats_tom.tests.factories import (
    DRAGONSRecipeFactory,
    DRAGONSReduceFactory,
)
from rest_framework.test import APITestCase


class TestDRAGONSReduceUpdateSerializer(APITestCase):
    """Test class for `DRAGONSReduceUpdateSerializer`."""

    def setUp(self):
        self.recipe = DRAGONSRecipeFactory()
        self.reduction = DRAGONSReduceFactory(recipe=self.recipe, status="running")

    def test_valid_update(self):
        """Test updating `DRAGONSReduce` with valid status change."""
        valid_data = {"status": "canceled"}
        serializer = DRAGONSReduceUpdateSerializer(self.reduction, data=valid_data)

        self.assertTrue(
            serializer.is_valid(),
            msg=f"Serializer should be valid. Errors: {serializer.errors}",
        )

        updated_reduction = serializer.save()
        self.assertEqual(
            updated_reduction.status,
            "canceled",
            "Reduction status should be updated to 'canceled'.",
        )
        self.assertTrue(
            updated_reduction.end_time is not None,
            "End time should be updated when canceled.",
        )

    def test_invalid_update_terminal_state(self):
        """Test updating `DRAGONSReduce` when it is already in a terminal state."""
        self.reduction.status = "done"
        self.reduction.save()
        invalid_data = {"status": "canceled"}
        serializer = DRAGONSReduceUpdateSerializer(self.reduction, data=invalid_data)

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should not be valid when trying to update from a terminal state.",
        )
        self.assertIn(
            "status",
            serializer.errors,
            "Error message should include 'status' field when updating from a terminal state.",
        )

    def test_invalid_update_wrong_status(self):
        """Test updating `DRAGONSReduce` with an incorrect status value."""
        invalid_data = {
            "status": "running",
        }  # Assuming 'running' cannot be set directly
        serializer = DRAGONSReduceUpdateSerializer(self.reduction, data=invalid_data)

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should not be valid when given an incorrect status value.",
        )
        self.assertIn(
            "status",
            serializer.errors,
            "Error message should include 'status' field for incorrect status value.",
        )
