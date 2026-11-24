__all__ = ["WorkflowStateSerializer"]

from typing import Any

from gpp_client.generated.enums import ObservationWorkflowState
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class WorkflowStateSerializer(_BaseGPPSerializer):
    """The workflow state asked for.

    Parameters
    ----------
    optional : bool, optional
        Whether the state may be left out, for an existing observation whose
        state the user did not change: GPP keeps it as it is.
    """

    workflowStateSelect = serializers.ChoiceField(
        choices=[c.value for c in ObservationWorkflowState],
        required=True,
        allow_blank=False,
        allow_null=False,
    )

    pydantic_model = None

    def __init__(self, *args: Any, optional: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["workflowStateSelect"].required = not optional

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
    def workflow_state(self) -> str | None:
        """Get the workflow state value.

        Returns
        -------
        str | None
            The workflow state value, or ``None`` when it was left out.
        """
        return self.validated_data.get("workflowStateSelect")

    @property
    def workflow_state_enum(self) -> ObservationWorkflowState | None:
        """Get the workflow state enum.

        Returns
        -------
        ObservationWorkflowState | None
            The workflow state enum, or ``None`` when it was left out.
        """
        state = self.workflow_state
        return ObservationWorkflowState(state) if state else None
