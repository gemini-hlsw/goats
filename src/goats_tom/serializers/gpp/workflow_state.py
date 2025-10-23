__all__ = ["WorkflowStateSerializer"]

from typing import Any

from gpp_client.api.enums import ObservationWorkflowState
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class WorkflowStateSerializer(_BaseGPPSerializer):
    workflowStateSelect = serializers.ChoiceField(
        choices=[c.value for c in ObservationWorkflowState],
        required=True,
        allow_blank=False,
        allow_null=False,
    )

    pydantic_model = None

    def _format_gpp(self) -> dict[str, Any]:
        """
        Format the workflow state data for GPP.

        Parameters
        ----------
        data : dict[str, Any]
            The validated data dictionary.

        Returns
        -------
        dict[str, Any]
            The formatted data dictionary for GPP.
        """
        return {"state": self.workflow_state}

    @property
    def workflow_state(self) -> str:
        """Get the workflow state value.

        Returns
        -------
        str
            The workflow state value.
        """
        return self.validated_data["workflowStateSelect"]

    @property
    def workflow_state_enum(self) -> ObservationWorkflowState:
        """Get the workflow state enum.

        Returns
        -------
        ObservationWorkflowState
            The workflow state enum.
        """
        return ObservationWorkflowState(self.workflow_state)
