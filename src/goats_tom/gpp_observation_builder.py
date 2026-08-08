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

# GPP rejects a target created without one: RA, Dec and epoch must all be
# given together. The schema marks it optional, so this only surfaces as a
# server-side error at creation time -- "Argument 'input.SET.sidereal' is
# invalid". Matches the value GOATS already sends from
# `goats_tom.serializers.gpp.sidereal`, and ANTARES publishes J2000
# coordinates, so it is right rather than merely a placeholder.
DEFAULT_EPOCH = "J2000.000"

# ANTARES reports its passband as a bare letter; GPP names the same filters
# after the Sloan system. Matched case-insensitively because surveys are not
# consistent about it (``g`` and ``R`` both occur).
ANTARES_TO_GPP_BAND = {
    "u": "SLOAN_U",
    "g": "SLOAN_G",
    "r": "SLOAN_R",
    "i": "SLOAN_I",
    "z": "SLOAN_Z",
    # Y has no Sloan equivalent in GPP; the enum names it plainly.
    "y": "Y",
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


async def clone_observation_for_target(
    client,
    program_id: str,
    template_observation_id: str,
    target,
    workflow_state=None,
    overrides=None,
    source_profile=None,
    on_created=None,
    target_overrides=None,
    template_target_id: str = "",
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
        The state to set on the new observation, as an enum member or its
        name. `None` means ``READY``, which is the useful default for
        automatic triggering -- an observation left inactive would still need
        somebody to notice and activate it, which is the manual step being
        removed. A PI who wants review before observing can choose another
        state in the template editor.

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

    `on_created` exists because that recording is otherwise impossible. The
    ids are only returned on the happy path, so a failure in step 3 used to
    lose them entirely -- the caller could not tell an observation had been
    created and would treat the attempt as having cost nothing. The hook is
    called synchronously, in this event loop, and must not touch the database:
    Django's ORM raises `SynchronousOnlyOperation` when called from async
    context. Pass a plain in-memory collector and persist after the await.

    A coroutine, not a sync function. Every GPP call here must share one event
    loop with the caller's other calls on the same `client`: `async_to_sync`
    opens a fresh loop per call and closes it on return, which leaves the
    client's connection pool bound to a dead loop and fails the next call with
    ``Event loop is closed``. The one `async_to_sync` belongs at the top of
    `goats_tom.gemini_trigger.trigger_gemini_observation`, around everything.
    """
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

    # No default to READY. The state is a deliberate choice made in the
    # template picker, and silently promoting an observation to READY means
    # committing telescope time the PI did not ask to commit. Nothing set
    # means leave GPP's own state alone.
    if workflow_state is None or workflow_state == "":
        workflow_state = None
    elif isinstance(workflow_state, str):
        # Accepted as a string so callers can pass a stored value straight
        # through. An unrecognised one falls back to READY rather than
        # raising: the observation already exists by this point, and refusing
        # to set any state would leave it stranded.
        try:
            workflow_state = ObservationWorkflowState(workflow_state.upper())
        except ValueError:
            # Left unset rather than forced to READY: an unrecognised value
            # means the configuration is not understood, and guessing READY
            # would schedule an observation on the strength of a typo.
            logger.warning(
                "Unknown workflow state %r; leaving the observation's state "
                "as GPP created it.",
                workflow_state,
            )
            workflow_state = None

    # 1. Produce the target for this locus.
    #
    # Cloned from the template's target when there is one, exactly as the
    # interactive path does, so everything the picker configured is inherited
    # -- above all the SED, which an ANTARES alert does not carry and which
    # cannot be invented. Only the per-locus facts are overridden: name,
    # coordinates, and the brightness from the alert.
    #
    # Building one from scratch instead produced targets with an empty source
    # profile on every automatic trigger, since a bare
    # `TargetPropertiesInput` has whatever the caller puts in it and nothing
    # else.
    target_kwargs = dict(target_overrides or {})
    for per_locus in ("name", "sidereal", "nonsidereal"):
        target_kwargs.pop(per_locus, None)
    target_kwargs.pop("sourceProfile", None)
    target_kwargs["name"] = target.name
    target_kwargs["sidereal"] = SiderealInput(
        ra=RightAscensionInput(degrees=target.ra),
        dec=DeclinationInput(degrees=target.dec),
        epoch=DEFAULT_EPOCH,
    )
    if source_profile is not None:
        # Only when the alert actually gave a magnitude and a band. Otherwise
        # the inherited profile stands, which is better than replacing a
        # configured SED with a bare brightness.
        target_kwargs["source_profile"] = source_profile

    target_properties = TargetPropertiesInput(**target_kwargs)

    if template_target_id:
        clone_target_result = await client.target.clone(
            template_target_id, properties=target_properties
        )
        target_dump = clone_target_result.model_dump(by_alias=True)
        new_target_id = (
            target_dump.get("cloneTarget", {}).get("newTarget", {}).get("id")
        )
    else:
        # No template target recorded -- a subscription configured before the
        # picker stored one. Degraded but working: no inherited profile.
        logger.warning(
            "No template target for programme %s; creating a bare target, "
            "which will have no SED. Re-apply the template on the ingestion "
            "page to fix this.",
            program_id,
        )
        create_target_result = await client.target.create_by_program_id(
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

    if on_created is not None:
        on_created(target_id=new_target_id, observation_id=None)

    # 2. Clone the template, overriding only the target it points at.
    #    Everything else -- instrument, exposure, conditions -- is inherited,
    #    which is the whole point of using a template.
    try:
        subtitle = _goats_subtitle()
    except Exception:  # noqa: BLE001
        # Logged, not silent. A bare "GOATS" badge is a real loss of
        # traceability in Explore and previously left no trace of why.
        logger.warning("Could not determine the GOATS version.", exc_info=True)
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
    # GPP computes an observation's workflow state in the background and the
    # clone mutation selects that field, so asked too soon the clone *errors*
    # even though the observation was created. The id then exists only inside
    # the message. The interactive path has recovered it for a while; this one
    # used to abandon the observation and report a plain failure, leaving it
    # orphaned in Explore and -- because nothing was recorded -- uncounted
    # against the trigger cap.
    new_observation = None
    try:
        clone_result = await client.observation.clone(input=clone_input)
    except Exception as clone_error:
        from goats_tom.api_views.gpp.observations import (  # noqa: PLC0415
            GPPObservationViewSet,
        )

        recovered_id = GPPObservationViewSet._observation_id_from_clone_error(
            clone_error
        )
        if recovered_id is None:
            raise
        logger.warning(
            "Clone reported a pending background calculation; continuing "
            "with observation %s, which was created.",
            recovered_id,
        )
        new_observation_id = recovered_id
    else:
        clone_dump = clone_result.model_dump(by_alias=True)
        new_observation = clone_dump.get("cloneObservation", {}).get(
            "newObservation", {}
        )
        new_observation_id = new_observation.get("id")

    if new_observation_id is None:
        raise RuntimeError(
            "GPP did not return an id for the cloned observation. A target "
            f"({new_target_id}) may have been left behind in the programme."
        )

    # Announced before step 3, not after. Step 3 is the one that realistically
    # fails -- it polls for up to a minute -- and by then the observation is
    # already real and already spending the allocation.
    if on_created is not None:
        on_created(target_id=new_target_id, observation_id=new_observation_id)

    # 3. Set the workflow state. Retried by the client itself, because GPP
    #    needs a moment after a clone before the new observation will accept a
    #    state change.
    new_state = None
    if workflow_state is not None:
        # The retry is what waits out the same background calculation that can
        # make the clone reply fail, which is why the re-fetch below can
        # succeed afterwards.
        new_state = await client.workflow_state.update_by_id_with_retry(
            observation_id=new_observation_id,
            workflow_state=workflow_state,
            max_attempts=55,
            initial_delay=5,
            retry_delay=1,
        )

    # 4. Fill in the observation itself when the clone reply never arrived.
    #    Recording it in GOATS needs its reference label, not just its id, so
    #    a stub will not do. Done here rather than at the point of failure
    #    because the wait above has by now given GPP time to answer.
    if new_observation is None:
        try:
            fetched = await client.observation.get_by_id(
                observation_id=new_observation_id
            )
            new_observation = fetched.model_dump(by_alias=True).get(
                "observation", {}
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Could not re-fetch observation %s after a pending "
                "calculation; it exists in GPP but cannot be recorded in "
                "GOATS.",
                new_observation_id,
            )
            new_observation = None

    return {
        "target_id": new_target_id,
        "observation_id": new_observation_id,
        "workflow_state": new_state,
        "observation": new_observation,
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
    # From `context_processors`, not `utils`. It was imported from the latter,
    # which raised `ImportError` on every call -- swallowed by the caller's
    # bare `except`, so every automatically-created observation was badged a
    # bare "GOATS" with no version, silently and always.
    from goats_tom.context_processors import get_goats_version  # noqa: PLC0415

    return f"GOATS:{get_goats_version()}"
