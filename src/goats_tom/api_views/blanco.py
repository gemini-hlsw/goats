"""Serves the BLANCO observation form to the interface that draws it.

The toolkit's form stays in charge: it declares the fields, their types and
their limits, and this hands that description to the browser. The interface
never invents a field, and never restates what the form already says.
"""

__all__ = ["BLANCOObservationViewSet"]

from typing import Any

from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from tom_targets.models import Target

from goats_tom.facilities import BLANCOFacility
from goats_tom.facilities.blanco import ALWAYS_REQUIRED
from goats_tom.facilities.instrument_schema import EXTRA
from goats_tom.forms.form_schema import describe_form

#: The form BLANCO offers.
OBSERVATION_TYPE = "IMAGING"

#: What the portal asks for above the configurations, in reading order.
DETAILS_FIELDS = [
    "name",
    "proposal",
    "observation_mode",
    "ipp_value",
    "acceptability_threshold",
    "configuration_repeats",
    "optimization_type",
]

#: When the request may be observed. The portal calls this the window. One
#: window is sent, as the toolkit sends one.
WINDOW_FIELDS = ["start", "end"]

#: How often to repeat the observation inside that window. Left blank the
#: request is observed once.
CADENCE_FIELDS = ["period", "jitter"]

#: What a configuration asks for, in the order the portal asks it. Whatever
#: the chosen instrument declares follows, since only it knows what it takes.
CONFIGURATION_FIELDS = [
    "c_{index}_instrument_type",
    "c_{index}_configuration_type",
    "c_{index}_target_override",
]

#: The configuration field that only means something when the request's
#: target keeps company: it substitutes another target of the same group.
TARGET_OVERRIDE = "c_{index}_target_override"

#: A reading order for the instrument parameters; the rest follow as declared.
PARAMETER_ORDER = [
    "dither_sequence",
    "dither_value",
    "dither_sequence_random_offset",
    "detector_centering",
]

#: What one exposure asks for, in the order the portal asks it. Whatever the
#: chosen instrument declares follows.
EXPOSURE_FIELDS = [
    "c_{index}_ic_{exposure}_exposure_count",
    "c_{index}_ic_{exposure}_exposure_time",
    "c_{index}_ic_{exposure}_filter",
    "c_{index}_ic_{exposure}_readout_mode",
    "c_{index}_ic_{exposure}_offset_ra",
    "c_{index}_ic_{exposure}_offset_dec",
]

#: A reading order for the exposure parameters.
EXPOSURE_PARAMETER_ORDER = ["coadds", "sequence_repeats"]

#: What a configuration will and will not observe through.
CONSTRAINT_FIELDS = [
    "c_{index}_max_airmass",
    "c_{index}_min_lunar_distance",
    "c_{index}_max_lunar_phase",
]

#: What the toolkit's own view asks for besides the fields on show. The
#: interface posts them back untouched when it submits.
HIDDEN_FIELDS = ["facility", "observation_type", "target_id"]

#: The fields that take a whole row instead of half of one (see FULL).
WIDTHS: dict[str, int] = {}


def _constants(target_id: str) -> dict[str, Any]:
    """What every request through this endpoint is, whoever asks."""
    return {
        "target_id": target_id,
        "facility": BLANCOFacility.name,
        "observation_type": OBSERVATION_TYPE,
    }


def _required(fields: list[dict], suffixes: tuple[str, ...]) -> list[dict]:
    """Say which fields have to be answered, whatever the toolkit declares.

    The form cannot require them of every exposure it carries, only of the
    ones drawn, so it asks for them when it is filled in; here is where that
    is said in advance, which is when it is worth saying.
    """
    for field in fields:
        if field["name"].endswith(suffixes):
            field["required"] = True
    return fields


def _demanded(form: Any) -> tuple[str, ...]:
    """What an exposure has to answer: ours, and what an instrument insists on."""
    return ALWAYS_REQUIRED + tuple(
        f"{EXTRA}_{name}"
        for name, spec in form.exposure_parameters().items()
        if spec.get("required")
    )


def _messages(form: Any) -> dict[str, list[str]]:
    """The errors as plain words, by the field they were raised on."""
    return {
        name: [error["message"] for error in errors]
        for name, errors in form.errors.get_json_data().items()
    }


def _configuration_fields(form: Any, index: int) -> list[str]:
    """What a configuration asks for, in the order the portal asks it."""
    names = [name.format(index=index) for name in CONFIGURATION_FIELDS]
    override = TARGET_OVERRIDE.format(index=index)
    # A target that keeps no company has nothing to be substituted by: the
    # only target on offer would be the one the request already names.
    if len(form.fields[override].choices) < 2:
        names.remove(override)
    return names


def _ordered(parameters: dict[str, dict], order: list[str]) -> list[str]:
    """The parameters, the known ones first, in a reading order."""
    known = [name for name in order if name in parameters]
    return known + sorted(name for name in parameters if name not in order)


class BLANCOObservationViewSet(ViewSet):
    """Describes the BLANCO form, section by section."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        """Return the sections the interface draws, in order."""
        target_id = request.query_params.get("target_id")
        if not target_id:
            return Response(
                {"detail": "A target_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not Target.objects.filter(pk=target_id).exists():
            return Response(
                {"detail": f"No target {target_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        form = self._form(target_id)
        return Response(
            {
                "sections": [
                    self._details(form),
                    self._configuration(form),
                    self._window(form),
                ],
                # Only the chosen instrument's parameters apply, and only the
                # values it allows; the interface narrows itself with this.
                "instruments": form.narrowing(),
                "hidden": {name: form.initial.get(name) for name in HIDDEN_FIELDS},
            }
        )

    def create(self, request: Request) -> Response:
        """Say whether what was filled in would be accepted.

        Nothing is observed here: the answer comes back for the interface to
        show, and the observation itself is submitted through the toolkit's
        own view, which is what keeps the record of it.
        """
        target_id = request.data.get("target_id")
        if not target_id:
            return Response(
                {"detail": "A target_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = self._bound(target_id, request.data.get("fields") or {})
        # What is checked here is checked first. The toolkit asks the portal
        # whatever it has, and builds the payload to ask with; put to it
        # before the form holds a name, it raises instead of reporting.
        if not form.errors and form.is_valid():
            return Response({"valid": True, "message": form.get_validation_message()})
        return Response({"valid": False, "errors": _messages(form)})

    @staticmethod
    def _details(form: Any) -> dict[str, Any]:
        """The section that opens the form."""
        return {
            "title": "Details",
            "open": True,
            "fields": describe_form(form, DETAILS_FIELDS, WIDTHS),
        }

    @staticmethod
    def _window(form: Any) -> dict[str, Any]:
        """The section that says when the request may be observed."""
        return {
            "title": "Window",
            "open": True,
            "fields": describe_form(form, WINDOW_FIELDS, WIDTHS),
            # A cadence is what turns that one window into a rhythm, so it
            # belongs with the window and nowhere else.
            "sections": [
                {
                    "title": "Cadence",
                    "open": True,
                    "fields": describe_form(form, CADENCE_FIELDS, WIDTHS),
                }
            ],
        }

    @staticmethod
    def _configuration(form: Any) -> dict[str, Any]:
        """The section that says what the telescope is asked to do.

        A request repeats its configuration as many times as the facility
        allows, so every one it could carry is described. The interface draws
        the first and adds the rest as they are asked for; what it never drew
        is never sent, and never built.
        """
        return {
            "title": "Configuration",
            "open": True,
            "repeat": "configuration",
            "instances": [
                {
                    "id": index,
                    "fields": describe_form(
                        form,
                        _configuration_fields(form, index)
                        + [
                            f"c_{index}_{EXTRA}_{parameter}"
                            for parameter in _ordered(
                                form.parameters(), PARAMETER_ORDER
                            )
                        ],
                        WIDTHS,
                    ),
                    # The portal puts the exposures and the constraints inside
                    # the configuration they belong to, and so does this.
                    "sections": [
                        BLANCOObservationViewSet._exposures(form, index),
                        BLANCOObservationViewSet._constraints(form, index),
                    ],
                }
                for index in form.configurations()
            ],
        }

    @staticmethod
    def _exposures(form: Any, index: int) -> dict[str, Any]:
        """The section that says what the exposures of a configuration take."""
        return {
            "title": "Exposures",
            "open": True,
            "repeat": "exposure",
            "instances": [
                {
                    "id": exposure,
                    "fields": _required(
                        describe_form(
                            form,
                            [
                                name.format(index=index, exposure=exposure)
                                for name in EXPOSURE_FIELDS
                            ]
                            + [
                                f"c_{index}_ic_{exposure}_{EXTRA}_{parameter}"
                                for parameter in _ordered(
                                    form.exposure_parameters(),
                                    EXPOSURE_PARAMETER_ORDER,
                                )
                            ],
                            WIDTHS,
                        ),
                        _demanded(form),
                    ),
                }
                for exposure in form.exposures()
            ],
        }

    @staticmethod
    def _constraints(form: Any, index: int) -> dict[str, Any]:
        """The section that says what the sky has to be like."""
        names = [name.format(index=index) for name in CONSTRAINT_FIELDS]
        return {
            "title": "Constraints",
            "open": True,
            "fields": describe_form(form, names, WIDTHS),
        }

    @staticmethod
    def _form(target_id: str) -> Any:
        """Build the toolkit's form, unbound."""
        form_class = BLANCOFacility().get_form(OBSERVATION_TYPE)
        return form_class(initial=_constants(target_id))

    @staticmethod
    def _bound(target_id: str, fields: dict[str, Any]) -> Any:
        """Build the toolkit's form over what was filled in."""
        form_class = BLANCOFacility().get_form(OBSERVATION_TYPE)
        # The endpoint is the BLANCO imaging one, so what it is asked to
        # check is a BLANCO imaging request, whatever was posted.
        return form_class(data={**fields, **_constants(target_id)})
