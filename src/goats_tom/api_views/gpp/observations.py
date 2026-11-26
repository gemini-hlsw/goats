"""Handles grabbing observations and observation details from GPP."""

__all__ = ["GPPObservationViewSet"]

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List

from asgiref.sync import async_to_sync
from gpp_client import GPPClient
from gpp_client.exceptions import GPPWorkflowTransitionError
from gpp_client.generated.enums import (
    AttachmentType,
    CalculationState,
    Existence,
    ObservationValidationCodeSeverity,
    ObservationWorkflowState,
    TooActivation,
)
from gpp_client.generated.exceptions import GraphQLClientGraphQLMultiError
from gpp_client.generated.input_types import (
    CreateObservationInput,
    ScienceRequirementsInput,
    SpectroscopyScienceRequirementsInput,
    TargetEnvironmentInput,
    WavelengthInput,
)
from httpx import TimeoutException
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory
from rest_framework.viewsets import GenericViewSet, mixins
from tom_observations.api_views import ObservationRecordViewSet
from tom_observations.models import ObservationRecord

from goats_tom.context_processors.goats_version_processor import get_goats_version
from goats_tom.credentials import get_credentials
from goats_tom.models import GPPLogin
from goats_tom.realtime import GPPProgress
from goats_tom.serializers.gpp import (
    ContextSerializer,
    CreateContextSerializer,
    ObservationSerializer,
    TargetSerializer,
    WorkflowStateSerializer,
)
from goats_tom.serializers.gpp.instruments.gmos.exposure_mode import (
    ExposureModeSerializer,
)

from ._credentials import GPPCredentialsMixin

logger = logging.getLogger(__name__)

#: What it takes to edit a target or observation the account may only view.
NOT_EDITABLE_REASON = (
    "Editing needs the PI, Co-I or support role in the program; ask the PI to "
    "change your role."
)

#: A stage GPP turned down; GPP's own messages follow it.
NOT_ACCEPTED_MESSAGE = "GPP did not accept the changes"

#: A form GOATS could not send; the fields to fix follow it.
FORM_ERRORS_MESSAGE = "Fix these fields and try again"

#: GPP did not answer, so whether it did what was asked is not known.
TIMEOUTS = (TimeoutError, TimeoutException)
TIMEOUT_MESSAGE = "GPP did not respond in time."

#: A check that found nothing.
CHECKED_MESSAGE = "Checked"

#: The state of an observation that was not saved.
NOT_ATTEMPTED_MESSAGE = "Not attempted"

#: The states GPP gives an observation for what its validation finds, as opposed
#: to those a user or an execution sets.
VALIDATION_STATES = (
    ObservationWorkflowState.UNDEFINED,
    ObservationWorkflowState.UNAPPROVED,
    ObservationWorkflowState.DEFINED,
)

#: A request to save in GOATS only that did not go through.
NOT_SAVED_SUMMARY = "Observation not saved in GOATS"


class LeftOutError(Exception):
    """GPP left a target or observation out of an update, see ``left_out_error``.

    Parameters
    ----------
    message : str
        Why it was left out.
    *reasons : str
        What more there is to say about it.
    label : str
        Why it was left out, in a couple of words.
    """

    def __init__(self, message: str, *reasons: str, label: str) -> None:
        super().__init__(message)
        self.reasons = list(reasons)
        self.label = label


class Stage(str, Enum):
    """Stages in the observation creation process."""

    CREDENTIALS_CHECK = "Credentials Check"
    NORMALIZATION = "Data Normalization"
    VALIDATION = "Data Validation"
    CREATE_TARGET = "Create Sidereal Target"
    UPDATE_TARGET = "Update Sidereal Target"
    CREATE_OBSERVATION = "Create Observation"
    UPDATE_OBSERVATION = "Update Observation"
    UPDATE_WORKFLOW_STATE = "Update Workflow State"
    GOATS_OBSERVATION_SAVE = "Save Observation in GOATS"


class MessageStatus(str, Enum):
    """Status of a message in the observation creation process."""

    SUCCESS = "Success"
    ERROR = "Error"
    WARNING = "Warning"
    #: Left out because an earlier stage failed.
    SKIPPED = "Skipped"


class ResponseStatus(str, Enum):
    """Overall status of the observation creation response."""

    SUCCESS = "Success"
    PARTIAL_SUCCESS = "Partial Success"
    FAILURE = "Failure"


class StepLabel(str, Enum):
    """What the steps of the result say of a stage that failed: why, as the title of
    the result already says what was not done."""

    NOT_CONFIGURED = "Not configured"
    NOT_VALID = "Not valid"
    REFUSED = "Refused"
    NO_PERMISSION = "No permission"
    DELETED = "Deleted"
    NOT_CONFIRMED = "Not confirmed"
    FAILED = "Failed"
    #: The state of an observation that was saved, when GPP could not be asked.
    NOT_CHECKED = "Not checked"


@dataclass
class StageMessage:
    """Message for a specific stage in the observation creation process.

    ``message`` says what happened and ``details`` lists why, each reason as
    ``{"severity": "error" | "warning" | "note", "text": ...}``, errors first.
    ``label`` says it in a couple of words, for the steps of the result, when
    ``message`` is a whole sentence.
    """

    stage: Stage
    status: MessageStatus
    message: str
    details: list[dict[str, str]] = field(default_factory=list)
    label: str = ""


class ProgressMessages(list):
    """The messages of a request, each also sent to the page that made it as the
    stage ends, so that the page shows the steps while the request runs.

    Parameters
    ----------
    request : Request
        The request; its ``progressId`` names it for the page.
    """

    def __init__(self, request: Request) -> None:
        super().__init__()
        self._progress = GPPProgress(request.user.pk, request.data.get("progressId"))

    def append(self, message: StageMessage) -> None:
        super().append(message)
        self._progress.send(
            message.stage.value, message.status.value, message.label or message.message
        )


#: The labels of the checks, which fail in one way only.
CHECK_LABELS = {
    Stage.CREDENTIALS_CHECK: StepLabel.NOT_CONFIGURED,
    Stage.NORMALIZATION: StepLabel.NOT_VALID,
    Stage.VALIDATION: StepLabel.NOT_VALID,
}


def _format_workflow_state(workflow_state) -> str:
    state = getattr(workflow_state, "state", None)
    value = getattr(state, "value", None)
    return (value or "unknown").capitalize()


def _state_label(workflow_state: ObservationWorkflowState) -> str:
    """Name a workflow state as the form does, e.g. ``DEFINED`` as "Defined"."""
    return workflow_state.value.capitalize()


def left_out_error(
    get_by_id: Callable[..., Any], kind: str, item_id: str
) -> LeftOutError:
    """Find out why GPP left a target or observation out of an update.

    GPP updates only what exists and the account may edit, and reports nothing
    about the rest. What GOATS just listed is therefore either deleted since or
    in a program the account may only view. GPP has no query for the account's
    own role, so GOATS cannot check it first.

    Parameters
    ----------
    get_by_id : Callable[..., Any]
        The client method that gets the item, deleted or not.
    kind : str
        ``"target"`` or ``"observation"``, as GPP names it in the answer.
    item_id : str
        The ID of the item.

    Returns
    -------
    LeftOutError
        The error to raise.
    """
    try:
        answer = async_to_sync(get_by_id)(item_id).model_dump(by_alias=True)
    except GraphQLClientGraphQLMultiError as error:
        # GPP may answer and still report that it has no sequence for it.
        if not error.data:
            raise
        answer = error.data
    if (answer.get(kind) or {}).get("existence") == Existence.DELETED:
        return LeftOutError(f"{item_id} was deleted in GPP", label=StepLabel.DELETED)
    return LeftOutError(
        f"Your GPP account cannot edit {item_id}",
        NOT_EDITABLE_REASON,
        label=StepLabel.NO_PERMISSION,
    )


def _field_label(name: str | int) -> str:
    """Name a form field for people, e.g. ``hiddenObservingModeInput`` as
    "Observing mode", or a list index as "#1"."""
    if isinstance(name, int) or str(name).isdigit():
        return f"#{int(name) + 1}"
    name = re.sub(r"^hidden(?=[A-Z])", "", str(name))
    name = re.sub(r"(Select|Input|Textarea|Checkbox)$", "", name)
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).lower()
    return words[:1].upper() + words[1:]


def _form_errors(detail: Any, path: tuple = ()) -> list[str]:
    """Flatten the nested errors of a form into one line each.

    Parameters
    ----------
    detail : Any
        A ``ValidationError.detail``: a mapping, a list or a message.
    path : tuple, optional
        The fields leading to ``detail``.

    Returns
    -------
    list[str]
        Each error, prefixed with the field it is about, e.g.
        "Timing windows › #1 › End: End must contain either 'atUtc' or 'after'."
    """
    if isinstance(detail, dict):
        return [
            line
            for key, value in detail.items()
            # Errors about the whole of a nested form belong to its field.
            for line in _form_errors(
                value,
                path if key == api_settings.NON_FIELD_ERRORS_KEY else (*path, key),
            )
        ]
    if isinstance(detail, list):
        return [
            line
            for index, item in enumerate(detail)
            for line in _form_errors(
                item, (*path, index) if isinstance(item, (dict, list)) else path
            )
        ]
    prefix = " › ".join(_field_label(p) for p in path)
    text = str(detail).replace(
        "End must contain either 'atUtc' or 'after'.",
        "Specify an end time or a duration.",
    )
    return [f"{prefix}: {text}" if prefix else text]


def _stage_message(
    stage: Stage,
    status: MessageStatus,
    message: str,
    reasons: list[tuple[str, str]],
    label: str = "",
) -> StageMessage:
    """Build a message with its reasons, as severity and text."""
    return StageMessage(
        stage=stage,
        status=status,
        message=message,
        details=[{"severity": severity, "text": text} for severity, text in reasons],
        label=label,
    )


def stage_error(
    stage: Stage,
    error: Exception | str,
    lead: str | None = None,
    label: str | None = None,
    check: str | None = None,
    failed: str | None = None,
) -> StageMessage:
    """Describe a stage that failed and why.

    GPP can turn a request down for several reasons at once, and a form error
    comes as nested mappings: each reason is listed on its own.

    Parameters
    ----------
    stage : Stage
        The stage that failed.
    error : Exception | str
        What it raised.
    lead : str | None, optional
        What to say before the reasons of GPP or of the form, to be more precise
        than the messages they have by default.
    label : str | None, optional
        What the steps of the result say; by default, why the stage failed.
    check : str | None, optional
        What to check before trying again when GPP did not answer, e.g. "o-123".
    failed : str | None, optional
        What to say before an unexpected error, which does not say what it is about.

    Returns
    -------
    StageMessage
        The error message of the stage.
    """
    if isinstance(error, TIMEOUTS):
        message, reasons = TIMEOUT_MESSAGE, []
        if check is not None:
            message = f"{message} Check {check} before trying again."
        cause = StepLabel.NOT_CONFIRMED
    elif isinstance(error, GPPWorkflowTransitionError):
        message, reasons = lead or NOT_ACCEPTED_MESSAGE, _transition_reasons(error)
        cause = StepLabel.REFUSED
    elif isinstance(error, LeftOutError):
        message, reasons = str(error), [("note", reason) for reason in error.reasons]
        cause = error.label
    elif isinstance(error, GraphQLClientGraphQLMultiError):
        message = lead or NOT_ACCEPTED_MESSAGE
        reasons = [("error", e.message) for e in error.errors]
        cause = StepLabel.REFUSED
    elif isinstance(error, ValidationError):
        message = lead or FORM_ERRORS_MESSAGE
        reasons = [("error", line) for line in _form_errors(error.detail)]
        cause = StepLabel.FAILED
    else:
        # The client names the domain that raised an error, which means nothing here.
        text = re.sub(r"^(\w+Domain: )+", "", str(error)) or repr(error)
        message, reasons = (failed, [("error", text)]) if failed else (text, [])
        cause = StepLabel.FAILED
    return _stage_message(
        stage,
        MessageStatus.ERROR,
        message,
        reasons,
        label or CHECK_LABELS.get(stage, cause),
    )


def _with_lead(message: StageMessage, lead: str) -> StageMessage:
    """Give what a message says as the reason of a lead, unless it has reasons."""
    if not message.details:
        message.details = [{"severity": "error", "text": message.message}]
        message.message = lead
    return message


def _calculated_state(
    client: GPPClient, observation_id: str
) -> ObservationWorkflowState:
    """Ask GPP for the workflow state of an observation it has finished calculating.

    Raises
    ------
    RuntimeError
        When GPP is still calculating it, as the state it has may change.
    """
    result = async_to_sync(client.workflow_state.get_by_id)(
        observation_id=observation_id
    )
    workflow = result.observation.workflow
    if workflow.state != CalculationState.READY:
        raise RuntimeError(f"GPP is still calculating {observation_id}.")
    return workflow.value.state


def _transition_reasons(error: GPPWorkflowTransitionError) -> list[tuple[str, str]]:
    """Why GPP does not allow a workflow state: its reasons or, when it gives none,
    the states it does allow."""
    reasons = [(reason.severity.lower(), reason.message) for reason in error.reasons]
    if not reasons:
        allowed = ", ".join(state.capitalize() for state in error.allowed)
        reasons = [("error", f"GPP allows {allowed or 'no other state'}.")]
    return reasons


def state_error(
    client: GPPClient,
    error: Exception,
    observation_id: str,
    workflow_state: ObservationWorkflowState,
) -> StageMessage:
    """Describe a workflow state that was not set, and the one GPP has instead.

    Parameters
    ----------
    client : GPPClient
        The client to ask GPP with.
    error : Exception
        What setting the state raised.
    observation_id : str
        The ID of the observation.
    workflow_state : ObservationWorkflowState
        The state asked for.

    Returns
    -------
    StageMessage
        The message of the workflow state stage.
    """
    asked = _state_label(workflow_state)
    label = f"Not set to {asked}"
    lead = f"GPP did not set {observation_id} to {asked}"
    check = None
    if isinstance(error, TIMEOUTS):
        label = StepLabel.NOT_CONFIRMED
        lead = f"GPP did not confirm the change of {observation_id} to {asked}"
        check = observation_id
    try:
        state = _calculated_state(client, observation_id)
    except Exception as e:
        logger.warning("Could not check the workflow state", exc_info=e)
    else:
        label = _state_label(state)
        if state == workflow_state:
            # It was set all the same: only GPP's answer was lost.
            return _stage_message(
                Stage.UPDATE_WORKFLOW_STATE, MessageStatus.SUCCESS, label, []
            )
        lead = f"{observation_id} is {label}. GPP could not change its state to {asked}"
        # It was just checked.
        check = None
    # Whatever went wrong, what matters is the state that was not set.
    message = stage_error(Stage.UPDATE_WORKFLOW_STATE, error, lead, label, check)
    return _with_lead(message, lead)


def _not_saved_error(error: Exception, observation_id: str) -> StageMessage:
    """Describe an observation that GOATS did not save."""
    return _stage_message(
        Stage.GOATS_OBSERVATION_SAVE,
        MessageStatus.ERROR,
        f"GOATS did not save {observation_id}",
        [("error", str(error) or repr(error))],
        StepLabel.FAILED,
    )


def workflow_report(observation: Any) -> StageMessage:
    """Say what state GPP has an observation in, once it has recalculated it.

    An observation in a state its validation gives (Undefined, Unapproved, or
    Defined with warnings, which keep it from Ready) comes with GPP's reasons. A
    warning its program dismissed no longer keeps it from anything.

    Parameters
    ----------
    observation : Any
        The observation from ``workflow_state.get_by_id_when_ready()``.

    Returns
    -------
    StageMessage
        The message of the workflow state stage.
    """
    workflow = observation.workflow.value
    warning = ObservationValidationCodeSeverity.WARNING
    dismissed = observation.program.dismissed_warnings
    reasons = [
        (error.severity.value.lower(), text)
        for error in workflow.validation_errors
        if not (error.severity == warning and error.code in dismissed)
        for text in (error.messages or [error.code.value])
    ]
    # Errors are what keeps it back, so they come first.
    reasons.sort(key=lambda reason: reason[0] != "error")

    state = _state_label(workflow.state)
    if workflow.state not in VALIDATION_STATES or not reasons:
        return _stage_message(
            Stage.UPDATE_WORKFLOW_STATE, MessageStatus.SUCCESS, state, []
        )
    message = f"{observation.id} is {state}"
    if workflow.state == ObservationWorkflowState.DEFINED:
        message = f"{message}. These warnings keep it from Ready"
    return _stage_message(
        Stage.UPDATE_WORKFLOW_STATE, MessageStatus.WARNING, message, reasons, state
    )


def failure_summary(stage: Stage) -> str:
    """Say what a stage that failed kept from happening, for the title of the result.

    Parameters
    ----------
    stage : Stage
        The stage that failed.

    Returns
    -------
    str
        The summary.
    """
    # Up to validation, nothing has reached GPP.
    if stage in (Stage.CREDENTIALS_CHECK, Stage.NORMALIZATION, Stage.VALIDATION):
        return "Observation not sent to GPP"
    if stage in (Stage.CREATE_TARGET, Stage.CREATE_OBSERVATION):
        return "Observation not created"
    return "Observation not updated"


def summarize(
    messages: list[StageMessage],
    done: str,
    workflow_state: ObservationWorkflowState | None,
) -> str:
    """Say what happened to an observation GPP has, for the title of the result.

    Parameters
    ----------
    messages : list[StageMessage]
        The messages of every stage.
    done : str
        What GPP did with it, e.g. "Observation updated".
    workflow_state : ObservationWorkflowState | None
        The state asked for, ``None`` when it was left as it was.

    Returns
    -------
    str
        The summary.
    """
    failed = {m.stage for m in messages if m.status == MessageStatus.ERROR}
    if any(m.label == StepLabel.NOT_CONFIRMED for m in messages):
        return f"{done}; some results could not be confirmed"
    if not failed:
        state_report = next(
            (
                m
                for m in messages
                if m.stage == Stage.UPDATE_WORKFLOW_STATE
                and m.status == MessageStatus.WARNING
            ),
            None,
        )
        if state_report is not None:
            if state_report.label == StepLabel.NOT_CHECKED:
                return f"{done}; state could not be confirmed"
            return f"{done}; validation issues found"
        return done
    if failed == {Stage.UPDATE_WORKFLOW_STATE}:
        return f"{done}, but not set to {_state_label(workflow_state)}"
    if failed == {Stage.UPDATE_TARGET}:
        return f"{done}; target update failed"
    if failed == {Stage.GOATS_OBSERVATION_SAVE}:
        return f"{done}, but not saved in GOATS"
    return f"{done}, with problems"


def summarize_calibration(
    messages: list[StageMessage], workflow_state: ObservationWorkflowState | None
) -> str:
    """Say what happened to a calibration, of which GOATS sets only the state.

    Parameters
    ----------
    messages : list[StageMessage]
        The messages of every stage.
    workflow_state : ObservationWorkflowState | None
        The state asked for, ``None`` when it was left as it was.

    Returns
    -------
    str
        The summary.
    """
    if workflow_state is None:
        return "No changes requested"
    if any(m.label == StepLabel.NOT_CONFIRMED for m in messages):
        return "Calibration state could not be confirmed"
    if any(m.status == MessageStatus.ERROR for m in messages):
        return "Calibration state could not be updated"
    return f"Calibration state updated to {_state_label(workflow_state)}"


def normalize_discovery_survey(discovery_survey: Any) -> str:
    """Normalize the discovery survey submitted by the observation form.

    Parameters
    ----------
    discovery_survey : Any
        Raw form value.

    Returns
    -------
    str
        The cleaned survey name, or an empty string when there is none.
    """
    if not isinstance(discovery_survey, str):
        return ""
    # Colons delimit the subtitle fields, so they cannot appear in the survey.
    return " ".join(discovery_survey.replace(":", " ").split())


def build_goats_subtitle(discovery_survey: str = "") -> str:
    """Build the GOATS identifier used as the GPP observation subtitle.

    Parameters
    ----------
    discovery_survey : str, optional
        Normalized survey the target was discovered by, appended as a suffix.

    Returns
    -------
    str
        ``"GOATS:<version>[:<survey>]"``, or ``"GOATS"`` if the version lookup
        fails.
    """
    try:
        subtitle = f"GOATS:{get_goats_version()}"
    except Exception:
        subtitle = "GOATS"

    return f"{subtitle}:{discovery_survey}" if discovery_survey else subtitle


def apply_goats_subtitle(observation_properties: Any, normalized_data: dict) -> None:
    """Set the GOATS identifier, including the discovery survey, as the subtitle.

    Parameters
    ----------
    observation_properties : Any
        Observation properties sent to GPP.
    normalized_data : dict
        Normalized form data holding ``"discoverySurveyInput"``.
    """
    discovery_survey = normalize_discovery_survey(
        normalized_data.get("discoverySurveyInput")
    )
    observation_properties.subtitle = build_goats_subtitle(discovery_survey)


def apply_too_activation_labels(
    target_properties: Any, observation_properties: Any, normalized_data: dict
) -> None:
    """Label a ToO with its activation in the title and the observer notes.

    Parameters
    ----------
    target_properties : Any
        Target properties sent to GPP.
    observation_properties : Any
        Observation properties sent to GPP.
    normalized_data : dict
        Normalized form data holding ``"tooActivationSelect"``.
    """
    activation = normalized_data.get("tooActivationSelect")
    if not activation or activation == TooActivation.NONE.value:
        return

    # GPP builds the observation title from its targets' names.
    name = target_properties.name or ""
    if not name.startswith(f"{activation} "):
        target_properties.name = f"{activation} {name}".strip()

    notes = observation_properties.observer_notes or ""
    if activation not in notes.split():
        observation_properties.observer_notes = f"{activation}\n{notes}".strip()


def build_failure_response(
    stage: Stage,
    error: Exception | str,
    previous_messages: list[StageMessage],
    data: dict[str, Any] | None = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    overall_status: ResponseStatus = ResponseStatus.FAILURE,
    summary: str | None = None,
    lead: str | None = None,
    check: str | None = None,
    failed: str | None = None,
) -> Response:
    """Build a structured failure response and append an error message.

    Parameters
    ----------
    stage : Stage
        The stage at which the failure occurred.
    error : Exception | str
        The error that occurred.
    previous_messages : list[StageMessage]
        The list of messages from previous stages, to which the error is added.
    data : dict[str, Any] | None = None
        Additional data to include in the response.
    http_status : int = status.HTTP_400_BAD_REQUEST
        The HTTP status code for the response.
    overall_status : ResponseStatus = ResponseStatus.FAILURE
        The overall status of the response.
    summary : str | None = None
        What happened, for the title of the result; by default, what
        ``failure_summary`` says of the stage.
    lead : str | None = None
        What to say before the reasons, see ``stage_error``.
    check : str | None = None
        What to check when GPP did not answer, see ``stage_error``.
    failed : str | None = None
        What to say before an unexpected error, see ``stage_error``.

    Returns
    -------
    Response
        The response containing the failure details.
    """
    error_message = str(error) or repr(error)
    # The traceback tells where an unexpected error came from, which its message
    # alone often does not. A form error is expected and says it all.
    unexpected = isinstance(error, Exception) and not isinstance(error, ValidationError)
    logger.error(
        "Error at stage %s: %s",
        stage.value,
        error_message,
        exc_info=error if unexpected else None,
    )
    previous_messages.append(
        stage_error(stage, error, lead, check=check, failed=failed)
    )
    # Without its target, the observation was not created for sure.
    if stage == Stage.CREATE_OBSERVATION and isinstance(error, TIMEOUTS):
        summary = "Observation creation could not be confirmed"

    return Response(
        {
            "status": overall_status,
            "summary": summary or failure_summary(stage),
            "messages": [asdict(msg) for msg in previous_messages],
            "data": data or {},
        },
        status=http_status,
    )


class GPPObservationViewSet(GPPCredentialsMixin, GenericViewSet, mixins.ListModelMixin):
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def _normalize_finder_charts(self, data):
        """
        Normalize finder chart data for serializer consumption.

        Parameters
        ----------
        data : dict
            Incoming request data.

        Returns
        -------
        dict
            Updated data with normalized ``finderCharts``.
        """
        raw_finder_charts = json.loads(data.pop("finderCharts", "{}"))

        to_add = []
        for item in raw_finder_charts.get("toAdd", []):
            file_key = item.get("fileKey")
            file_obj = data.pop(file_key, None)

            if not file_obj:
                continue

            to_add.append(
                {
                    "description": item.get("description", ""),
                    "file": file_obj,
                    "overwrite": bool(item.get("overwrite", False)),
                }
            )

        data["finderCharts"] = {
            "toAdd": to_add,
            "toDelete": raw_finder_charts.get("toDelete", []),
            "toUnassign": raw_finder_charts.get("toUnassign", []),
        }

        return data

    def _get_program_finder_charts(
        self, client: GPPClient, program_id: str
    ) -> dict[str, str]:
        """
        Map the file names of the finder charts already stored in a program.

        Parameters
        ----------
        client : GPPClient
            Authenticated GPP client.
        program_id : str
            Program owning the attachments.

        Returns
        -------
        dict[str, str]
            Lowercased file name mapped to the attachment id.
        """
        try:
            payload = async_to_sync(client.attachment.get_all_by_program_id)(
                program_id=program_id
            )
            program = payload.model_dump(by_alias=True).get("program") or {}
        except Exception as e:
            raise ValueError(
                f"Failed to fetch attachments for program '{program_id}': {e}"
            ) from e

        return {
            str(a["fileName"]).lower(): str(a["id"])
            for a in program.get("attachments") or []
            if a.get("attachmentType") == AttachmentType.FINDER
        }

    def _process_finder_charts(
        self,
        client: GPPClient,
        observation_id: str,
        program_id: str,
        finder_charts: dict[str, Any],
    ) -> list[str]:
        to_delete = {str(i) for i in finder_charts.get("toDelete", [])}
        to_unassign = {str(i) for i in finder_charts.get("toUnassign", [])}
        to_add = finder_charts.get("toAdd", [])

        # GPP stores attachments at program level, so unassigning only drops the
        # observation's reference while deleting removes the file for everyone.
        for attachment_id in sorted(to_delete):
            try:
                async_to_sync(client.attachment.delete_by_id)(
                    attachment_id=attachment_id
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to delete finder chart '{attachment_id}': {e}"
                ) from e
        try:
            attachment_result = async_to_sync(
                client.attachment.get_all_by_observation_id
            )(observation_id=observation_id)
            attachment_data = (
                attachment_result.model_dump(by_alias=True).get("observation") or {}
            )
        except Exception as e:
            raise ValueError(
                f"Failed to fetch current finder charts for observation "
                f"'{observation_id}': {e}"
            ) from e

        removed = to_delete | to_unassign
        currentIds = [
            a["id"]
            for a in attachment_data.get("attachments", [])
            if str(a["id"]) not in removed
        ]
        # add new finder charts to program
        return self._upload_finder_charts(
            client=client,
            program_id=program_id,
            to_add=to_add,
            current_ids=currentIds,
        )

    def _upload_finder_charts(
        self,
        client: GPPClient,
        program_id: str,
        to_add: list[dict[str, Any]],
        current_ids: list[str] | None = None,
    ) -> list[str]:
        """Upload finder charts to a program and return the attachment IDs.

        Parameters
        ----------
        client : GPPClient
            The client used to talk to GPP.
        program_id : str
            The program the charts are stored in.
        to_add : list[dict[str, Any]]
            The charts to upload, as normalized by the form.
        current_ids : list[str] | None, optional
            Attachment IDs the observation already references.

        Returns
        -------
        list[str]
            The attachment IDs the observation should reference.
        """
        attachment_ids = list(current_ids or [])

        if not to_add:
            return attachment_ids

        program_charts = self._get_program_finder_charts(client, program_id)

        for item in to_add:
            description = item.get("description", "")
            file = item.get("file")

            if not file:
                continue

            file.seek(0)
            # GPP rejects duplicate file names within a program, so a chart
            # already stored under the same name is reused, keeping its id so
            # other observations referencing it stay valid.
            existing_id = program_charts.get(file.name.lower())

            if existing_id is not None:
                # Replacing the stored content needs the confirmation the
                # editor asks for; otherwise the chart is simply attached.
                if item.get("overwrite"):
                    try:
                        async_to_sync(client.attachment.update_by_id)(
                            attachment_id=existing_id,
                            file_name=file.name,
                            description=description or None,
                            content=file.read(),
                        )
                    except Exception as e:
                        raise ValueError(
                            f"Failed to overwrite finder chart '{file.name}': {e}"
                        ) from e

                if existing_id not in attachment_ids:
                    attachment_ids.append(existing_id)
                continue

            try:
                newId = async_to_sync(client.attachment.upload)(
                    program_id=program_id,
                    attachment_type=AttachmentType("FINDER"),
                    file_name=file.name,
                    description=description,
                    content=file.read(),
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to upload finder chart '{file.name}': {e}"
                ) from e

            attachment_ids.append(newId)
            program_charts[file.name.lower()] = str(newId)

        return attachment_ids

    def _build_science_requirements(
        self, data: dict[str, Any], observing_mode: str
    ) -> ScienceRequirementsInput | None:
        """Build the science requirements of an observation created from scratch.

        Parameters
        ----------
        data : dict[str, Any]
            The normalized form data.
        observing_mode : str
            The observing mode of the new observation.

        Returns
        -------
        ScienceRequirementsInput | None
            The science requirements, or ``None`` if the form carried none.
        """
        exposure_time_mode = None
        if data.get("exposureModeSelect"):
            exposure_mode_serializer = ExposureModeSerializer(data=data)
            exposure_mode_serializer.is_valid(raise_exception=True)
            exposure_time_mode = exposure_mode_serializer.to_pydantic()

        spectroscopy = None
        central_wavelength = data.get("centralWavelengthInput")
        if observing_mode.endswith("LONG_SLIT") and central_wavelength:
            spectroscopy = SpectroscopyScienceRequirementsInput(
                wavelength=WavelengthInput(nanometers=float(central_wavelength))
            )

        if exposure_time_mode is None and spectroscopy is None:
            return None

        return ScienceRequirementsInput(
            exposure_time_mode=exposure_time_mode,
            spectroscopy=spectroscopy,
        )

    def _normalize_form_data(self, request: Request) -> dict[str, Any]:
        """
        Normalize form data by stripping whitespace and converting empty strings to
        ``None``.

        Parameters
        ----------
        request : Request
            The HTTP request object containing form data.

        Returns
        -------
        dict[str, Any]
            The normalized form data.
        """
        return {key: self._normalize(value) for key, value in request.data.items()}

    def _normalize(self, value: str | None) -> str | None:
        """
        Convert empty strings or whitespace to ``None``.

        Parameters
        ----------
        value : str | None
            The input string to normalize.

        Returns
        -------
        str | None
            The normalized string or ``None`` if the input was empty or whitespace.
        """
        if isinstance(value, str):
            return value.strip() or None
        return value

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return a list of GPP observations associated with the authenticated user.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing a list of GPP observations.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        """
        if (denied := self.missing_credentials(request)) is not None:
            return denied

        credentials = request.user.gpplogin
        program_id = request.query_params.get("program_id")

        try:
            # Setup client to communicate with GPP.
            client = GPPClient(token=credentials.token)
            if program_id is not None:
                logger.debug(
                    "Retrieving GPP observations for program ID: %s", program_id
                )
                payload = async_to_sync(client.goats.get_observations_by_program_id)(
                    program_id=program_id
                )
                data = payload.model_dump(by_alias=True)["observations"]
                # One list with every observation, each flagged so the select
                # can group them by type. The ToO select is fed by the approved
                # configuration requests, not by observations.
                matches = data.get("matches", [])
                observations = [{**o, "isToo": self.is_too(o)} for o in matches]

                # Build the custom data response.
                return Response(
                    {
                        "matches": {
                            "count": len(observations),
                            "results": observations,
                        },
                        "hasMore": data.get("hasMore", False),
                    }
                )
            else:
                logger.debug(
                    "Retrieving all GPP observations for user: %s", request.user
                )
                payload = async_to_sync(client.observation.get_all)()
                return Response(payload.model_dump(by_alias=True))
        except Exception as e:
            logger.exception("Error retrieving GPP observations")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # FIXME: Should I be getting "opportunity" from "firstScienceTarget" instead of the
    # list of asterisms?
    def is_too(self, obs: dict) -> bool:
        """Return whether the observation is a Target of Opportunity (ToO).

        Parameters
        ----------
        obs : dict
            The observation payload returned from GPP. This may or may not
            contain the ``targetEnvironment`` and ``asterism`` keys.

        Returns
        -------
        bool
            ``True`` if the observation is a ToO (opportunity present), ``False``
            otherwise.
        """
        # Need to handle case where any of this data could be missing.
        # This fails silently and returns False if anything is missing.
        target_env = obs.get("targetEnvironment") or {}
        asterisms = target_env.get("asterism") or []
        if not asterisms:
            return False
        return bool(asterisms[0].get("opportunity"))

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Return details for a specific GPP observation by observation ID.

        Parameters
        ----------
        request : Request
            The HTTP request object, including user context.

        Returns
        -------
        Response
            A DRF Response object containing the details of the requested observation.

        Raises
        ------
        PermissionDenied
            If the authenticated user has not configured GPP login credentials.
        KeyError
            If 'pk' (the observation ID) is not present in kwargs.
        """
        # This is not in-use for right now but keeping it as a placeholder.
        observation_id = kwargs["pk"]

        if (denied := self.missing_credentials(request)) is not None:
            return denied
        credentials = request.user.gpplogin

        # Setup client to communicate with GPP.
        try:
            client = GPPClient(token=credentials.token)
            data = async_to_sync(client.observation.get_by_id)(
                observation_id=observation_id
            )
            return Response(data.model_dump(by_alias=True)["observation"])
        except Exception as e:
            logger.exception("Error retrieving GPP observation")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="save-only")
    def save_observation_only(self, request: Request, *args, **kwargs) -> Response:
        """Save an existing GPP observation to the GOATS database without creating a
        new one in GPP.

        Parameters
        ----------
        request : Request
            The request object containing the data for the observation to save.

        Returns
        -------
        Response
            A DRF Response object containing the details of the saved observation.
        """
        messages = ProgressMessages(request)
        data: dict[str, Any] = {}
        logger.info("Saving GPP observation to GOATS database")
        try:
            normalized_data = self._normalize_form_data(request)
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION,
                error=e,
                previous_messages=messages,
                summary=NOT_SAVED_SUMMARY,
            )
        messages.append(
            StageMessage(
                stage=Stage.NORMALIZATION,
                status=MessageStatus.SUCCESS,
                message=CHECKED_MESSAGE,
            )
        )

        logger.debug("Serializing context for GPP observation save")
        try:
            # Validate and extract required IDs for observation creation.
            context_serializer = ContextSerializer(data=normalized_data)
            context_serializer.is_valid(raise_exception=True)
            goats_target = context_serializer.goats_target
            instrument = context_serializer.instrument
            gpp_observation_id = context_serializer.gpp_observation_id
            formatted_observation = context_serializer.format_observation()

            messages.append(
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message=CHECKED_MESSAGE,
                )
            )

        except Exception as e:
            return build_failure_response(
                Stage.VALIDATION, e, messages, summary=NOT_SAVED_SUMMARY
            )

        # Save the existing observation to GOATS database.
        logger.debug("Creating GOATS observation record")
        try:
            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                observation=formatted_observation,
            )
            summary = "Observation saved in GOATS"

            if tom_response.status_code == status.HTTP_208_ALREADY_REPORTED:
                messages.append(
                    StageMessage(
                        stage=Stage.GOATS_OBSERVATION_SAVE,
                        status=MessageStatus.WARNING,
                        message=f"{gpp_observation_id} already saved",
                    )
                )
                summary = "Observation already in GOATS"

            elif tom_response.status_code != status.HTTP_201_CREATED:
                raise ValueError(tom_response.data)

            else:
                data["goatsObservation"] = tom_response.data
                messages.append(
                    StageMessage(
                        stage=Stage.GOATS_OBSERVATION_SAVE,
                        status=MessageStatus.SUCCESS,
                        message=f"{gpp_observation_id} saved",
                    )
                )

        except Exception as e:
            messages.append(_not_saved_error(e, gpp_observation_id))
            # Nothing else is done here, so the request failed as a whole.
            return self._build_structured_response(
                messages=messages,
                data=data,
                summary=NOT_SAVED_SUMMARY,
                overall_status=ResponseStatus.FAILURE,
            )

        return self._build_structured_response(
            messages=messages, data=data, summary=summary
        )

    @action(detail=False, methods=["post"], url_path="update-only")
    def update_only(self, request: Request, *args, **kwargs) -> Response:
        """Update an existing GPP observation.

        Parameters
        ----------
        request : Request
            The request object containing the data for the observation to update and
            save.

        Returns
        -------
        Response
            A DRF Response object containing the details of the updated observation.
        """
        messages = ProgressMessages(request)
        updated_target_id: str | None = None
        updated_observation_id: str | None = None
        observation_failed = False

        logger.info("Updating observation on GPP")

        # Ensure the user has GPP credentials.
        credentials = get_credentials(GPPLogin, user=request.user)
        if credentials is None:
            return build_failure_response(
                stage=Stage.CREDENTIALS_CHECK,
                error="GPP login credentials are not configured for this user.",
                previous_messages=messages,
            )

        messages.append(
            StageMessage(
                stage=Stage.CREDENTIALS_CHECK,
                status=MessageStatus.SUCCESS,
                message=CHECKED_MESSAGE,
            )
        )

        logger.debug("Normalizing form data for GPP observation update")
        try:
            normalized_data = self._normalize_form_data(request)
            normalized_data = self._normalize_finder_charts(normalized_data)
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION, error=e, previous_messages=messages
            )
        messages.append(
            StageMessage(
                stage=Stage.NORMALIZATION,
                status=MessageStatus.SUCCESS,
                message=CHECKED_MESSAGE,
            )
        )

        logger.debug("Serializing data for GPP observation update")
        # Calibrations are read-only except for their workflow state, so their
        # target/observation serializers and updates are skipped.
        is_calibration = normalized_data.get("isCalibration")
        client = None
        try:
            # Setup client to communicate with GPP.
            client = GPPClient(token=credentials.token)

            # Serialize and validate workflow state; left out, GPP keeps it.
            workflow_state_serializer = WorkflowStateSerializer(
                data=normalized_data, optional=True
            )
            workflow_state_serializer.is_valid(raise_exception=True)
            workflow_state = workflow_state_serializer.workflow_state_enum

            if not is_calibration:
                # Validate and extract required IDs for observation update.
                context_serializer = ContextSerializer(data=normalized_data)
                context_serializer.is_valid(raise_exception=True)
                gpp_target_id = context_serializer.gpp_target_id
                gpp_observation_id = context_serializer.gpp_observation_id
                gpp_program_id = context_serializer.gpp_program_id
                goats_target = context_serializer.goats_target

                # Serialize and validate target.
                target_serializer = TargetSerializer(data=normalized_data)
                target_serializer.is_valid(raise_exception=True)
                target_properties = target_serializer.to_pydantic()
                target_properties.name = (
                    normalized_data.get("titleInput") or goats_target.name
                )
                # Serialize and validate observation.
                observation_serializer = ObservationSerializer(data=normalized_data)
                observation_serializer.is_valid(raise_exception=True)
                observation_properties = observation_serializer.to_pydantic()

                # Set subtitle to a GOATS identifier for easier tracking.
                apply_goats_subtitle(observation_properties, normalized_data)
            else:
                # Only the observation ID is needed to update the workflow state.
                gpp_observation_id = normalized_data.get("hiddenObservationIdInput")
                if not gpp_observation_id:
                    raise ValueError("Missing observation ID for calibration update.")

            messages.append(
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message=CHECKED_MESSAGE,
                )
            )

        except Exception as e:
            observation_id = normalized_data.get("hiddenObservationIdInput")
            return build_failure_response(
                Stage.VALIDATION,
                e,
                messages,
                lead=(
                    f"Fix these fields of {observation_id} and try again"
                    if observation_id
                    else None
                ),
            )

        # Calibrations only update the workflow state; skip target/observation.
        if not is_calibration:
            # Update target.
            logger.debug("Updating sidereal target in GPP")
            try:
                update_target_result = async_to_sync(client.target.update_by_id)(
                    gpp_target_id, properties=target_properties
                )
                update_target_dump = update_target_result.model_dump(by_alias=True)
                targets = update_target_dump.get("updateTargets", {}).get("targets", [])
                updated_target_id = targets[0].get("id") if targets else None

                if updated_target_id is None:
                    raise left_out_error(
                        client.target.get_by_id, "target", gpp_target_id
                    )

                messages.append(
                    StageMessage(
                        stage=Stage.UPDATE_TARGET,
                        status=MessageStatus.SUCCESS,
                        message=f"{updated_target_id} updated",
                    )
                )

            except Exception as e:
                # Continue to observation update even if target update fails.
                messages.append(
                    stage_error(
                        Stage.UPDATE_TARGET,
                        e,
                        f"GPP did not accept the changes to {gpp_target_id}",
                        check=gpp_target_id,
                        failed=f"GOATS could not update {gpp_target_id}",
                    )
                )

            # Update observation.
            logger.debug("Updating observation in GPP")
            try:
                finder_charts = normalized_data.get("finderCharts") or {}

                if any(
                    finder_charts.get(k) for k in ("toAdd", "toDelete", "toUnassign")
                ):
                    finder_chart_ids = self._process_finder_charts(
                        client=client,
                        observation_id=gpp_observation_id,
                        program_id=gpp_program_id,
                        finder_charts=finder_charts,
                    )
                    observation_properties.attachments = finder_chart_ids

                # where = WhereObservation(id=WhereOrderObservationId
                # (eq=gpp_observation_id))
                reported = None
                try:
                    update_observation_result = async_to_sync(
                        client.observation.update_by_id
                    )(
                        observation_id=gpp_observation_id,
                        properties=observation_properties,
                    )
                    update_observation_dump = update_observation_result.model_dump(
                        by_alias=True
                    )
                except GraphQLClientGraphQLMultiError as error:
                    # GPP answers with the observation it saved and an error when
                    # it cannot generate its sequence. Without it, GPP refused it.
                    reported = error
                    update_observation_dump = error.data or {}
                observations_list = (
                    update_observation_dump.get("updateObservations") or {}
                ).get("observations") or []
                updated_observation_id = (
                    observations_list[0].get("id") if observations_list else None
                )

                if updated_observation_id is None:
                    raise reported or left_out_error(
                        client.observation.get_by_id, "observation", gpp_observation_id
                    )
                if reported is not None:
                    logger.warning(
                        "GPP saved observation %s and reported: %s",
                        updated_observation_id,
                        reported,
                    )

                messages.append(
                    StageMessage(
                        stage=Stage.UPDATE_OBSERVATION,
                        status=MessageStatus.SUCCESS,
                        message=f"{updated_observation_id} updated",
                    )
                )

            except Exception as e:
                observation_failed = True
                messages.append(
                    stage_error(
                        Stage.UPDATE_OBSERVATION,
                        e,
                        f"GPP did not accept the changes to {gpp_observation_id}",
                        check=gpp_observation_id,
                        failed=f"GOATS could not update {gpp_observation_id}",
                    )
                )

        # Set workflow state, unless the observation was not saved: GPP would judge
        # the state on the observation it still has, so its reasons (such as a
        # missing band the form had set) would not be about what the form shows.
        if observation_failed:
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SKIPPED,
                    message=NOT_ATTEMPTED_MESSAGE,
                )
            )
        # Nor when the form left it as it was read: then GPP keeps it, and GOATS
        # does not send back a state the user did not choose.
        elif workflow_state is None and is_calibration:
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SUCCESS,
                    message=f"{gpp_observation_id} unchanged",
                )
            )
        elif workflow_state is None:
            # The edit may still have changed what GPP makes of the observation (a
            # band set takes it from Undefined to Defined, say). GPP marks it for
            # recalculation as it saves the edit, so once ready it answers with the
            # state after it.
            logger.debug("Checking the workflow state of the updated observation")
            try:
                observation = async_to_sync(client.workflow_state.get_by_id_when_ready)(
                    gpp_observation_id, max_attempts=60, retry_delay=1
                )
                messages.append(workflow_report(observation))
            except Exception as e:
                # The changes are saved all the same.
                logger.warning("Could not check the workflow state", exc_info=e)
                lead = (
                    f"Could not retrieve the observation state of "
                    f"{gpp_observation_id} from GPP"
                )
                report = stage_error(
                    Stage.UPDATE_WORKFLOW_STATE, e, lead, StepLabel.NOT_CHECKED
                )
                report.status = MessageStatus.WARNING
                messages.append(_with_lead(report, lead))
        else:
            logger.debug("Setting workflow state for updated GPP observation")
            try:
                new_workflow_state = async_to_sync(
                    client.workflow_state.update_by_id_with_retry
                )(
                    observation_id=gpp_observation_id,
                    workflow_state=workflow_state,
                    max_attempts=55,
                    initial_delay=5,
                    retry_delay=1,
                )
                report = StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SUCCESS,
                    message=_format_workflow_state(new_workflow_state),
                )
            except Exception as e:
                # Continue to saving observation even if workflow state update fails.
                report = state_error(client, e, gpp_observation_id, workflow_state)
            # No other step of a calibration says which one it is.
            if is_calibration and report.status == MessageStatus.SUCCESS:
                report.message = f"{gpp_observation_id} {report.message}"
            messages.append(report)
        if client is not None:
            try:
                async_to_sync(client.close)()
            except Exception:
                logger.debug("Failed to close GPP client.", exc_info=True)

        failed = any(m.status == MessageStatus.ERROR for m in messages)
        if observation_failed:
            summary = (
                "Observation update could not be confirmed"
                if any(
                    m.stage == Stage.UPDATE_OBSERVATION
                    and m.label == StepLabel.NOT_CONFIRMED
                    for m in messages
                )
                else failure_summary(Stage.UPDATE_OBSERVATION)
            )
        elif is_calibration:
            summary = summarize_calibration(messages, workflow_state)
        else:
            summary = summarize(messages, "Observation updated", workflow_state)
        return self._build_structured_response(
            messages=messages,
            data={
                "updatedTargetId": updated_target_id,
                "updatedObservationId": updated_observation_id,
            },
            summary=summary,
            # Without the observation, or the state of a calibration, the request
            # failed as a whole, whatever else went through.
            overall_status=(
                ResponseStatus.FAILURE
                if observation_failed or (is_calibration and failed)
                else None
            ),
        )

    @action(detail=False, methods=["post"], url_path="create-and-save")
    def create_and_save_observation(
        self, request: Request, *args, **kwargs
    ) -> Response:
        """Create a sidereal target, observation, and sets the workflow in GPP.

        The steps taken to create a observation are:
        1. Clone the target with new properties, setting the target as sidereal.
        2. Clone the observation with new properties, linking to the new target.
        3. Set the workflow state for the new observation.

        Parameters
        ----------
        request : Request
            The request object containing the data for the new target and observation.

        Returns
        -------
        Response
            A DRF Response object containing the details of the created observation.
        """
        messages = ProgressMessages(request)
        new_target_id: str | None = None
        new_observation_id: str | None = None
        goats_observation: dict[str, Any] | None = None

        logger.info(
            "Creating observation on GPP and saving observation to GOATS database"
        )

        # Ensure the user has GPP credentials.
        credentials = get_credentials(GPPLogin, user=request.user)
        if credentials is None:
            return build_failure_response(
                stage=Stage.CREDENTIALS_CHECK,
                error="GPP login credentials are not configured for this user.",
                previous_messages=messages,
            )

        messages.append(
            StageMessage(
                stage=Stage.CREDENTIALS_CHECK,
                status=MessageStatus.SUCCESS,
                message=CHECKED_MESSAGE,
            )
        )

        logger.debug("Normalizing form data for GPP observation creation")
        try:
            normalized_data = self._normalize_form_data(request)
            normalized_data = self._normalize_finder_charts(normalized_data)
        except Exception as e:
            return build_failure_response(
                stage=Stage.NORMALIZATION, error=e, previous_messages=messages
            )
        messages.append(
            StageMessage(
                stage=Stage.NORMALIZATION,
                status=MessageStatus.SUCCESS,
                message=CHECKED_MESSAGE,
            )
        )

        logger.debug("Serializing data for GPP observation creation")
        client = None
        try:
            # Setup client to communicate with GPP.
            client = GPPClient(token=credentials.token)

            # Validate and extract required IDs for observation creation.
            context_serializer = CreateContextSerializer(data=normalized_data)
            context_serializer.is_valid(raise_exception=True)
            gpp_program_id = context_serializer.gpp_program_id
            goats_target = context_serializer.goats_target
            instrument = context_serializer.instrument

            # Serialize and validate target.
            target_serializer = TargetSerializer(data=normalized_data)
            target_serializer.is_valid(raise_exception=True)
            target_properties = target_serializer.to_pydantic()
            target_properties.name = (
                normalized_data.get("titleInput") or goats_target.name
            )
            # Serialize and validate observation.
            observation_serializer = ObservationSerializer(data=normalized_data)
            observation_serializer.is_valid(raise_exception=True)
            observation_properties = observation_serializer.to_pydantic()

            # Set subtitle to a GOATS identifier for easier tracking.
            apply_goats_subtitle(observation_properties, normalized_data)
            # Only new observations are labelled with their ToO activation.
            apply_too_activation_labels(
                target_properties, observation_properties, normalized_data
            )

            # Nothing is cloned, so the science requirements are built from what
            # the form submitted. GPP derives binning, ROI, read mode and the
            # dithers from the setup itself, so those are left out.
            science_requirements = self._build_science_requirements(
                normalized_data, instrument
            )
            if science_requirements is not None:
                observation_properties.science_requirements = science_requirements

            # Serialize and validate workflow state.
            workflow_state_serializer = WorkflowStateSerializer(data=normalized_data)
            workflow_state_serializer.is_valid(raise_exception=True)
            workflow_state = workflow_state_serializer.workflow_state_enum

            messages.append(
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message=CHECKED_MESSAGE,
                )
            )

        except Exception as e:
            return build_failure_response(Stage.VALIDATION, e, messages)
        # Create target.
        logger.debug("Creating sidereal target in GPP")
        try:
            create_target_result = async_to_sync(client.target.create_by_program_id)(
                gpp_program_id, properties=target_properties
            )
            create_target_dump = create_target_result.model_dump(by_alias=True)
            new_target_id = (
                create_target_dump.get("createTarget", {}).get("target", {}).get("id")
            )

            if new_target_id is None:
                raise ValueError("Failed to retrieve new target ID from create result.")

            messages.append(
                StageMessage(
                    stage=Stage.CREATE_TARGET,
                    status=MessageStatus.SUCCESS,
                    message=f"{new_target_id} created",
                )
            )

        except Exception as e:
            return build_failure_response(
                Stage.CREATE_TARGET,
                e,
                messages,
                lead="GPP did not accept the target",
                check="whether it created the target",
                failed="GOATS could not create the target",
            )

        # Create observation.
        logger.debug("Creating observation in GPP")
        try:
            observation_properties.target_environment = TargetEnvironmentInput(
                asterism=[new_target_id]
            )

            # The observation is new, so only the charts the user added apply:
            # there is no source observation to inherit or unassign from.
            finder_charts = normalized_data.get("finderCharts") or {}
            if finder_charts.get("toAdd"):
                observation_properties.attachments = self._upload_finder_charts(
                    client=client,
                    program_id=gpp_program_id,
                    to_add=finder_charts["toAdd"],
                )

            create_input = CreateObservationInput(
                program_id=gpp_program_id,
                set_=observation_properties,
            )
            try:
                create_observation_result = async_to_sync(client.observation.create)(
                    input=create_input,
                )
                create_observation_dump = create_observation_result.model_dump(
                    by_alias=True
                )
            except Exception as error_create:
                if "background calculation" not in str(error_create):
                    raise
                create_observation_dump = error_create.data or {}

            new_observation = create_observation_dump.get("createObservation", {}).get(
                "observation", {}
            )
            new_observation_id = new_observation.get("id")

            if new_observation_id is None:
                raise ValueError(
                    "Failed to retrieve new observation ID from create result."
                )

            messages.append(
                StageMessage(
                    stage=Stage.CREATE_OBSERVATION,
                    status=MessageStatus.SUCCESS,
                    message=f"{new_observation_id} created",
                )
            )

        except Exception as e:
            if client is not None:
                try:
                    async_to_sync(client.close)()
                except Exception:
                    logger.debug("Failed to close GPP client.", exc_info=True)
            return build_failure_response(
                Stage.CREATE_OBSERVATION,
                e,
                messages,
                lead="GPP did not accept the observation",
                check="whether it created the observation",
                failed="GOATS could not create the observation",
            )

        # Set workflow state.
        logger.debug("Setting workflow state for new GPP observation")
        try:
            new_workflow_state = async_to_sync(
                client.workflow_state.update_by_id_with_retry
            )(
                observation_id=new_observation_id,
                workflow_state=workflow_state,
                max_attempts=55,
                initial_delay=5,
                retry_delay=1,
            )
            messages.append(
                StageMessage(
                    stage=Stage.UPDATE_WORKFLOW_STATE,
                    status=MessageStatus.SUCCESS,
                    message=_format_workflow_state(new_workflow_state),
                )
            )

        except Exception as e:
            messages.append(state_error(client, e, new_observation_id, workflow_state))

        # Save the created observation to GOATS database.
        logger.debug("Creating GOATS observation record")
        try:
            tom_response = self._create_goats_observation(
                request=request,
                target_id=goats_target.id,
                instrument=instrument,
                observation=new_observation,
            )

            if tom_response.status_code == status.HTTP_208_ALREADY_REPORTED:
                messages.append(
                    StageMessage(
                        stage=Stage.GOATS_OBSERVATION_SAVE,
                        status=MessageStatus.WARNING,
                        message="Already in GOATS",
                    )
                )
            elif tom_response.status_code != status.HTTP_201_CREATED:
                raise ValueError(tom_response.data)

            else:
                goats_observation = tom_response.data
                messages.append(
                    StageMessage(
                        stage=Stage.GOATS_OBSERVATION_SAVE,
                        status=MessageStatus.SUCCESS,
                        message="Saved",
                    )
                )

        except Exception as e:
            messages.append(_not_saved_error(e, new_observation_id))

        response_data: dict[str, Any] = {
            "newTargetId": new_target_id,
            "newObservationId": new_observation_id,
        }
        if goats_observation is not None:
            response_data["goatsObservation"] = goats_observation

        if client is not None:
            try:
                async_to_sync(client.close)()
            except Exception:
                logger.debug("Failed to close GPP client.", exc_info=True)

        return self._build_structured_response(
            messages=messages,
            data=response_data,
            summary=summarize(messages, "Observation created", workflow_state),
        )

    def _create_goats_observation(
        self,
        request: Request,
        target_id: int,
        instrument: str,
        observation: dict[str, Any],
        facility: str = "GEM",
    ) -> Response:
        """
        Save the created GPP observation to the GOATS database using the TOM API
        view.

        Parameters
        ----------
        request : Request
            The DRF request object.
        target_id : int
            The ID of the GOATS target to associate with the observation.
        instrument : str
            The observation type (e.g., "GMOS_SOUTH_LONG_SLIT").
        observation : dict[str, Any]
            The observation data returned from GPP.
        facility : str, default="GEM"
            The facility name.

        Returns
        -------
        Response
            The DRF response from the TOM ObservationRecordViewSet.
        """
        # Check for existing ObservationRecord.
        observation_id = observation.get("reference", {}).get("label")
        if ObservationRecord.objects.filter(
            target_id=target_id,
            facility=facility,
            observation_id=observation_id,
        ).exists():
            logger.debug("ObservationRecord already exists for %s", observation_id)
            return Response(
                {
                    "detail": (
                        f"ObservationRecord already exists for {observation_id}"
                    ),
                },
                status=status.HTTP_208_ALREADY_REPORTED,
            )

        # Inject required fields into observation parameters.
        observation.update(
            {
                "target_id": target_id,
                "facility": facility,
            }
        )
        # 'observing_parameters' expects a payload matching the return of gpp-client.
        payload = {
            "target_id": target_id,
            "facility": facility,
            "observation_type": instrument,
            "observing_parameters": observation,
        }

        # Use APIRequestFactory to build an internal POST request.
        factory = APIRequestFactory()
        internal_request = factory.post("/api/observations/", payload, format="json")
        internal_request.user = request.user

        # Dispatch request to TOM view.
        view = ObservationRecordViewSet.as_view({"post": "create"})
        return view(internal_request)

    def _build_structured_response(
        self,
        messages: List[StageMessage],
        data: dict[str, Any],
        summary: str,
        status_code: int = status.HTTP_201_CREATED,
        overall_status: ResponseStatus | None = None,
    ) -> Response:
        """
        Build a structured response from the given messages and data.

        Parameters
        ----------
        messages : list[StageMessage]
            The list of stage messages.
        data : dict[str, Any]
            The data to include in the response.
        summary : str
            What happened, for the title of the result.
        status_code : int = status.HTTP_201_CREATED
            The HTTP status code for the response.
        overall_status : ResponseStatus | None = None
            The overall status, when the messages alone do not tell it.

        Returns
        -------
        Response
            The structured response.
        """
        # Determine final overall status and HTTP code.
        all_success = all(msg.status == MessageStatus.SUCCESS for msg in messages)
        final_status = overall_status or (
            ResponseStatus.SUCCESS if all_success else ResponseStatus.PARTIAL_SUCCESS
        )
        if not all_success:
            status_code = status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "status": final_status.value,
                "summary": summary,
                "messages": [asdict(msg) for msg in messages],
                "data": data,
            },
            status=status_code,
        )
