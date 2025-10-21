import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp import WorkflowStateSerializer
from gpp_client.api.enums import ObservationWorkflowState

# All enum values
VALID_VALUES = [state.value for state in ObservationWorkflowState]

@pytest.mark.parametrize(
    "input_data, expected_value",
    [
        *[( {"workflowStateSelect": value}, value ) for value in VALID_VALUES],
        ({}, None),  # Missing field should be valid
    ],
)
def test_valid_workflow_state(input_data: dict, expected_value: str | None) -> None:
    """Test valid enum values and missing field are accepted."""
    serializer = WorkflowStateSerializer(data=input_data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.workflow_state == expected_value
    if expected_value:
        assert serializer.workflow_state_enum == ObservationWorkflowState(expected_value)
    else:
        assert serializer.workflow_state_enum is None


@pytest.mark.parametrize(
    "input_data, expected_field, expected_message",
    [
        # Explicit None (e.g. null from JSON)
        ({"workflowStateSelect": None}, "workflowStateSelect", "This field may not be null."),
        # Invalid string
        ({"workflowStateSelect": "NOT_A_STATE"}, "workflowStateSelect", '"NOT_A_STATE" is not a valid choice.'),
        # Lowercase value (enum is case-sensitive)
        ({"workflowStateSelect": "ready"}, "workflowStateSelect", '"ready" is not a valid choice.'),
    ],
)
def test_invalid_workflow_state(input_data: dict, expected_field: str, expected_message: str) -> None:
    """Test invalid values are rejected with appropriate ValidationError."""
    serializer = WorkflowStateSerializer(data=input_data)
    with pytest.raises(ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)

    errors = exc_info.value.detail
    assert expected_field in errors
    assert any(expected_message in str(msg) for msg in errors[expected_field])
