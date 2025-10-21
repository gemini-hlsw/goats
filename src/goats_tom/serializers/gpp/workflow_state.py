__all__ = ["WorkflowStateSerializer"]

from gpp_client.api.enums import ObservationWorkflowState
from rest_framework import serializers

from ._base import _BaseSerializer


class WorkflowStateSerializer(_BaseSerializer):
    workflowStateSelect = serializers.ChoiceField(
        choices=[c.value for c in ObservationWorkflowState],
        required=False,
        allow_blank=False,
    )

    def validate(self, data: dict[str, str]) -> dict[str, str]:
        """
        Validate and return the data.

        Parameters
        ----------
        data : dict[str, str]
            The validated data dictionary.

        Returns
        -------
        dict[str, str]
            The validated data dictionary.
        """
        self._workflow_state = data.get("workflowStateSelect")
        self._workflow_state_enum = (
            ObservationWorkflowState(self._workflow_state)
            if self._workflow_state
            else None
        )
        return data

    @property
    def workflow_state(self) -> str | None:
        """Get the workflow state value.

        Returns
        -------
        str | None
            The workflow state value if set, otherwise None.
        """
        return getattr(self, "_workflow_state", None)

    @property
    def workflow_state_enum(self) -> ObservationWorkflowState | None:
        """Get the workflow state enum.

        Returns
        -------
        ObservationWorkflowState | None
            The workflow state enum if set, otherwise None.
        """
        return getattr(self, "_workflow_state_enum", None)
