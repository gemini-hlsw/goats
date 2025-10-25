import pytest
from gpp_client.api.enums import ObservationWorkflowState
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import WorkflowStateSerializer

VALID_VALUES = [state.value for state in ObservationWorkflowState]


@pytest.mark.parametrize(
    "input_value",
    VALID_VALUES,
)
def test_valid_workflow_state(input_value: str) -> None:
    """Ensure valid enum values are accepted and mapped correctly."""
    serializer = WorkflowStateSerializer(data={"workflowStateSelect": input_value})
    assert serializer.is_valid(), serializer.errors
    assert serializer.workflow_state == input_value
    assert serializer.workflow_state_enum == ObservationWorkflowState(input_value)


@pytest.mark.parametrize(
    "input_data, expected_field, expected_message",
    [
        ({}, "workflowStateSelect", "This field is required."),
        (
            {"workflowStateSelect": None},
            "workflowStateSelect",
            "This field may not be null.",
        ),
        (
            {"workflowStateSelect": ""},
            "workflowStateSelect",
            '"" is not a valid choice.',
        ),
        (
            {"workflowStateSelect": "NOT_A_STATE"},
            "workflowStateSelect",
            '"NOT_A_STATE" is not a valid choice.',
        ),
        (
            {"workflowStateSelect": "ready"},
            "workflowStateSelect",
            '"ready" is not a valid choice.',
        ),
    ],
)
def test_invalid_workflow_state(
    input_data: dict, expected_field: str, expected_message: str
) -> None:
    """Ensure invalid or missing values are rejected with specific ValidationError."""
    serializer = WorkflowStateSerializer(data=input_data)
    with pytest.raises(ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)

    errors = exc_info.value.detail
    assert expected_field in errors
    assert any(expected_message in str(msg) for msg in errors[expected_field])
