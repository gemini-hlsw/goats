"""Clone a GPP observation onto a new target, without needing a request.

The interactive path (`goats_tom.api_views.gpp.observations`) does this from
form data submitted by a browser: it reads `request.data` and `request.user`,
and reports progress back as staged messages. The ANTARES consumer has none of
those -- no request, no form, no signed-in user -- so it cannot call that view.

Rather than duplicate the clone-and-retarget sequence in a second place, where
a fix to one copy would silently miss the other, that sequence lives here as a
plain function taking explicit arguments.

The sequence itself is unchanged and deliberately ordered: clone the target
first, then clone the observation pointing at the new target, then set the
workflow state. Cloning the observation first would leave it briefly attached
to the *template's* target, which is a real object somebody else may be
observing.
"""

__all__ = ["ANTARES_TO_GPP_BAND", "clone_observation_for_target", "build_source_profile"]

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ANTARES reports its passband as a bare letter; GPP names the same filters
# after the Sloan system. Matched case-insensitively because surveys are not
# consistent about it (``g`` and ``R`` both occur).
ANTARES_TO_GPP_BAND = {
    "u": "SLOAN_U",
    "g": "SLOAN_G",
    "r": "SLOAN_R",
    "i": "SLOAN_I",
    "z": "SLOAN_Z",
}


def build_source_profile(magnitude, passband):
    """Build a point-source profile from one alert's brightness.

    Parameters
    ----------
    magnitude : float or None
        The alert magnitude.
    passband : str or None
        The passband as ANTARES reports it.

    Returns
    -------
    `SourceProfileInput` or None
        A point source with a single band brightness, or `None` if either
        input is missing or the passband is not one GPP knows.

    Notes
    -----
    Returns `None` rather than a partial profile whenever anything is missing.
    Brightness describes a real object on a real observation, so an incomplete
    or guessed value is worse than leaving the template's own: the observer
    would be told something specific and wrong. `None` means "no override",
    and the template's brightness stands.

    AB magnitudes, which is what ANTARES reports.
    """
    from gpp_client.generated.enums import Band, BrightnessIntegratedUnits
    from gpp_client.generated.input_types import (
        BandBrightnessIntegratedInput,
        BandNormalizedIntegratedInput,
        SourceProfileInput,
        SpectralDefinitionIntegratedInput,
    )

    if magnitude is None or not passband:
        return None

    band_name = ANTARES_TO_GPP_BAND.get(str(passband).strip().lower())
    if band_name is None:
        logger.warning(
            "ANTARES passband %r has no GPP equivalent; leaving the "
            "template's brightness in place.",
            passband,
        )
        return None

    return SourceProfileInput(
        point=SpectralDefinitionIntegratedInput(
            band_normalized=BandNormalizedIntegratedInput(
                brightnesses=[
                    BandBrightnessIntegratedInput(
                        band=Band(band_name),
                        value=float(magnitude),
                        units=BrightnessIntegratedUnits.AB_MAGNITUDE,
                    )
                ]
            )
        )
    )


def clone_observation_for_target(
    client,
    program_id: str,
    template_observation_id: str,
    target,
    workflow_state=None,
    overrides=None,
    source_profile=None,
) -> dict[str, Any]:
    """Clone a template observation and point it at `target`.

    Parameters
    ----------
    client : `gpp_client.GPPClient`
        An authenticated client.
    program_id : str
        The programme owning the template. Used to create the target in the
        right place.
    template_observation_id : str
        The observation to clone. Its instrument, exposure, conditions and
        constraints all carry over.
    target : `tom_targets.models.Target`
        The GOATS target supplying name and coordinates.
    overrides : dict, optional
        Observation properties to apply to the clone, overriding what the
        template carries. Applied to the copy only; the template is never
        modified, which is the whole reason overrides are stored on the
        subscription rather than saved back into GPP.
    source_profile : `SourceProfileInput`, optional
        Brightness for the new target, built from the triggering alert (see
        `build_source_profile`). `None` leaves the template's own brightness in
        place.
    workflow_state : optional
        The state to set on the new observation. Defaults to ``READY``, which
        is the point of automatic triggering -- an observation left inactive
        would still need somebody to notice and activate it, which is the
        manual step being removed.

    Returns
    -------
    dict
        ``{"target_id": ..., "observation_id": ..., "workflow_state": ...}``.

    Raises
    ------
    RuntimeError
        If GPP accepts a call but does not return the id that the next step
        depends on. Raised rather than returning a partial result, so the
        caller cannot mistake a half-finished clone for a working observation.

    Notes
    -----
    A failure after the observation clone leaves a real object in GPP. The
    caller is expected to record that (see
    `goats_tom.gemini_trigger.trigger_gemini_observation`) rather than retry,
    since a retry would create a second observation on the same target.
    """
    from asgiref.sync import async_to_sync
    from gpp_client.generated.enums import ObservationWorkflowState
    from gpp_client.generated.input_types import (
        CloneObservationInput,
        CoordinatesInput,
        DeclinationInput,
        ObservationPropertiesInput,
        RightAscensionInput,
        SiderealInput,
        TargetEnvironmentInput,
        TargetPropertiesInput,
    )

    if workflow_state is None:
        workflow_state = ObservationWorkflowState.READY

    # 1. Create the target in the programme, as a sidereal object at the
    #    locus's coordinates. Degrees, since that is how GOATS stores them.
    # Brightness belongs to the target, not the observation, so it is set
    # here rather than through the clone's property overrides.
    target_properties = TargetPropertiesInput(
        name=target.name,
        sidereal=SiderealInput(
            ra=RightAscensionInput(degrees=target.ra),
            dec=DeclinationInput(degrees=target.dec),
        ),
        source_profile=source_profile,
    )
    create_target_result = async_to_sync(client.target.create_by_program_id)(
        program_id=program_id, properties=target_properties
    )
    target_dump = create_target_result.model_dump(by_alias=True)
    new_target_id = (
        target_dump.get("createTarget", {}).get("target", {}).get("id")
    )
    if new_target_id is None:
        raise RuntimeError(
            "GPP did not return an id for the new target, so the observation "
            "cannot be linked to it."
        )

    # 2. Clone the template, overriding only the target it points at.
    #    Everything else -- instrument, exposure, conditions -- is inherited,
    #    which is the whole point of using a template.
    try:
        subtitle = _goats_subtitle()
    except Exception:  # noqa: BLE001
        subtitle = "GOATS"

    # Overrides first, then the two values GOATS always controls. Order
    # matters: the target must win, since pointing the clone at the new locus
    # is the entire purpose, and a stale target_environment left in a stored
    # override would silently observe the wrong object.
    properties_kwargs = dict(overrides or {})
    properties_kwargs["subtitle"] = subtitle
    properties_kwargs["target_environment"] = TargetEnvironmentInput(
        asterism=[new_target_id]
    )
    properties_kwargs.pop("targetEnvironment", None)

    clone_input = CloneObservationInput(
        observation_id=template_observation_id,
        set_=ObservationPropertiesInput(**properties_kwargs),
    )
    clone_result = async_to_sync(client.observation.clone)(input=clone_input)
    clone_dump = clone_result.model_dump(by_alias=True)
    new_observation_id = (
        clone_dump.get("cloneObservation", {})
        .get("newObservation", {})
        .get("id")
    )
    if new_observation_id is None:
        raise RuntimeError(
            "GPP did not return an id for the cloned observation. A target "
            f"({new_target_id}) may have been left behind in the programme."
        )

    # 3. Set the workflow state. Retried by the client itself, because GPP
    #    needs a moment after a clone before the new observation will accept a
    #    state change.
    new_state = async_to_sync(client.workflow_state.update_by_id_with_retry)(
        observation_id=new_observation_id,
        workflow_state=workflow_state,
        max_attempts=55,
        initial_delay=5,
        retry_delay=1,
    )

    return {
        "target_id": new_target_id,
        "observation_id": new_observation_id,
        "workflow_state": new_state,
    }


def _goats_subtitle() -> str:
    """Build the subtitle stamped on observations GOATS creates.

    Returns
    -------
    str
        e.g. ``"GOATS:26.8.0rc1"``.

    Notes
    -----
    Matches what the interactive path already writes, so automatically- and
    manually-created observations are identifiable the same way in Explore.
    """
    from goats_tom.utils import get_goats_version

    return f"GOATS:{get_goats_version()}"
