"""Automatic Gemini observation triggering for ANTARES loci.

Triggering clones a *template* observation the PI has already set up in GPP
and points the clone at the newly-saved target. That is how a ToO is normally
prepared by hand, so the PI configures instrument, exposure, conditions and
constraints in Explore -- where those tools already exist -- and GOATS only
repeats the clone-and-retarget step per alert.

Two guards run before anything is created, and either one refusing means no
observation is made:

- a lifetime cap on how many observations a subscription may create
  (`AntaresStreamSubscription.max_triggers`), and
- an allocation check: the template's expected execution time must fit in
  what is left of the programme's grant for that science band.

The allocation check is the one that actually protects the programme; the cap
is a blunter backstop for when the check cannot be made. Neither is a
substitute for the other, which is why both are enforced.
"""

__all__ = [
    "LOCUS_URL_TOKEN",
    "TriggerSkipped",
    "TriggerFailed",
    "trigger_gemini_observation",
]

import logging

from django.db import IntegrityError, transaction

from goats_tom.permissions import grant_observation_permissions

logger = logging.getLogger(__name__)

# Attempts to fetch the programme's allocation before giving up. Retried
# because this happens *before* anything is created, so a repeat is free -- no
# clone has been made, nothing can be duplicated. Everything after this point
# is deliberately not retried.
ALLOCATION_FETCH_ATTEMPTS = 3
ALLOCATION_FETCH_BACKOFF_SECONDS = 2.0

# Placeholder the template picker seeds into Observer Notes, replaced with the
# real ANTARES page for each triggered locus. A token rather than a literal URL
# because the template is configured before any locus exists, and every clone
# points at a different one.
LOCUS_URL_TOKEN = "{locus_url}"


def _locus_url(locus_id: str) -> str:
    """Build the ANTARES web page URL for a locus.

    Parameters
    ----------
    locus_id : str
        The ANTARES locus id.

    Returns
    -------
    str
        The locus page URL.

    Notes
    -----
    Built the same way `goats_tom.brokers.antares` builds it, so it follows the
    configured ANTARES environment rather than hardcoding production -- a
    development deployment should link to development.
    """
    from goats_tom.antares_client.config import ANTARESConfig  # noqa: PLC0415

    return f"{ANTARESConfig.get_url()}/loci/{locus_id}"


def _apply_locus_url(overrides: dict, locus_id: str) -> dict:
    """Substitute the locus URL token in Observer Notes.

    Parameters
    ----------
    overrides : dict
        The stored observation overrides.
    locus_id : str
        The locus being triggered.

    Returns
    -------
    dict
        A copy with the token replaced. The input is not modified, so the
        stored overrides keep the token for the next trigger.

    Notes
    -----
    Substitution only -- the link is never appended. If a PI removed the token
    from their notes, that is a deliberate choice and silently adding a URL
    back into text they edited would be surprising. The consequence is that
    notes without the token carry no link, which is what was asked for.
    """
    notes = (overrides or {}).get("observerNotes")
    if not notes or LOCUS_URL_TOKEN not in notes:
        return overrides

    updated = dict(overrides)
    updated["observerNotes"] = notes.replace(
        LOCUS_URL_TOKEN, _locus_url(locus_id)
    )
    return updated


class TriggerSkipped(Exception):
    """A guard declined to trigger. Not an error: a deliberate decision."""


class TriggerFailed(Exception):
    """Triggering was attempted and something went wrong."""


def _reserve_record(subscription, locus_id: str, run_number: int):
    """Claim this locus before contacting GPP.

    Parameters
    ----------
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription triggering.
    locus_id : str
        The locus prompting the trigger.
    run_number : int
        The subscription's run counter when the alert arrived.

    Returns
    -------
    `goats_tom.models.GeminiTriggerRecord`
        The newly-created pending record.

    Raises
    ------
    TriggerSkipped
        If this locus has already been attempted in this run.

    Notes
    -----
    Reserved *first*, before any GPP call, so the unique constraint on
    ``(subscription, run_number, locus_id)`` acts as an idempotency key. If a clone
    succeeds in GPP but the response is lost, the row already exists and a
    second attempt stops here rather than creating a duplicate observation and
    charging the allocation twice.

    An existing record for *this run* in any state stops the attempt,
    including a failed one: a failure after the clone began may have created
    an observation anyway, so retrying could double-charge. ANTARES re-alerts
    an active locus every few minutes, so an automatic retry would fire again
    almost immediately. The next run starts clean -- see the constraint on
    `goats_tom.models.GeminiTriggerRecord`.
    """
    from goats_tom.models import GeminiTriggerRecord  # noqa: PLC0415

    try:
        with transaction.atomic():
            return GeminiTriggerRecord.objects.create(
                subscription=subscription,
                run_number=run_number,
                locus_id=locus_id,
                status=GeminiTriggerRecord.STATUS_PENDING,
            )
    except IntegrityError as exc:
        raise TriggerSkipped(
            f"Locus {locus_id} has already been triggered in this "
            f"ingestion run."
        ) from exc


def _check_cap(subscription, record) -> None:
    """Refuse if the subscription has used its allowance.

    Parameters
    ----------
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription triggering.
    record : `goats_tom.models.GeminiTriggerRecord`
        This attempt's record, excluded from its own count.

    Raises
    ------
    TriggerSkipped
        If the cap has been reached.

    Notes
    -----
    Skipped attempts do not count (see
    `GeminiTriggerRecord.counts_towards_cap`): counting them would let a
    refusal consume the budget it was protecting, and once the cap was reached
    every further skip would hold it there. Nor do failures that never created
    an observation, for the same reason -- a cap on telescope time should be
    spent by observations, not by errors.

    Counted within one ingestion run. The cap belongs to the configuration it
    was set alongside -- a PI who stops, adjusts the setup and starts again is
    beginning a new campaign, not continuing the old one, and would otherwise
    find their allowance already spent by a configuration they have replaced.
    The band-time check (`_check_allocation`) is what bounds total spend across
    runs, since that reads the programme's real accounting from GPP.

    A blank cap means no limit. That is a deliberate choice a user has to make,
    not the default.
    """
    from goats_tom.models import GeminiTriggerRecord  # noqa: PLC0415

    if subscription.max_triggers is None:
        return

    # The SQL twin of `GeminiTriggerRecord.counts_towards_cap`; the two must
    # agree. Counted here rather than by iterating the property because a
    # subscription accumulates a row per locus and this runs on every trigger.
    #
    # Scoped to this run, matching the record uniqueness key. Failures with no
    # `gpp_observation_id` never created anything, so they release their slot
    # -- see the property for why. Pending rows still count:
    # one is in flight and about to create an observation, and not holding its
    # slot would let concurrent triggers overshoot the cap.
    used = (
        GeminiTriggerRecord.objects.filter(
            subscription=subscription, run_number=record.run_number
        )
        .exclude(status=GeminiTriggerRecord.STATUS_SKIPPED)
        .exclude(
            status=GeminiTriggerRecord.STATUS_FAILED,
            gpp_observation_id="",
        )
        .exclude(pk=record.pk)
        .count()
    )
    if used >= subscription.max_triggers:
        # States the fact, not the remedy. The remedy belongs on the
        # ingestion page next to the field that sets the limit, and repeating
        # it on every skipped row buried the one thing that differs between
        # them -- the count.
        raise TriggerSkipped(
            f"Trigger limit reached ({used} of {subscription.max_triggers} "
            f"used)."
        )


async def _fetch_band_time(client, program_id: str, observation_id: str):
    """Fetch granted and used time for the template's science band.

    Parameters
    ----------
    client : `gpp_client.GPPClient`
        An authenticated client.
    program_id : str
        The programme owning the template.
    observation_id : str
        The template observation, used to pick which band to check.

    Returns
    -------
    tuple
        ``(band, allocated_hours, used_hours)``.

    Raises
    ------
    TriggerFailed
        If GPP cannot be reached after `ALLOCATION_FETCH_ATTEMPTS`, or the
        template is not in the programme.

    Notes
    -----
    This is the accounting Explore shows: granted time per science band
    (``allocations``) against time already used (``timeCharge``). Matched to
    the template's own band, since a programme may hold separate grants per
    band and spending Band 3 time on a Band 1 observation would be wrong.

    Deliberately says nothing about what the *next* observation will cost. An
    earlier version required an execution time for the template and refused
    without one -- which could never work: GPP does not compute a cost for an
    unexecuted observation, and the field is not even returned by this query.
    The check is therefore "is there time left in this band", not "does this
    observation fit"; no client can do better, and the trigger cap remains the
    second line of defence.

    Retried, unlike everything after it, because nothing has been created yet
    -- a repeated read cannot duplicate anything. The retry sleeps with
    `asyncio.sleep`, not `time.sleep`: this runs inside the caller's event
    loop, and blocking it would stall the client's own transport.
    """
    import asyncio  # noqa: PLC0415

    last_error: Exception | None = None
    for attempt in range(1, ALLOCATION_FETCH_ATTEMPTS + 1):
        try:
            payload = await client.goats.get_observations_by_program_id(
                program_id=program_id
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Time accounting lookup for program %s failed "
                "(attempt %d/%d): %s",
                program_id,
                attempt,
                ALLOCATION_FETCH_ATTEMPTS,
                exc,
            )
            if attempt < ALLOCATION_FETCH_ATTEMPTS:
                await asyncio.sleep(ALLOCATION_FETCH_BACKOFF_SECONDS * attempt)
    else:
        raise TriggerFailed(
            f"Could not read the programme's time accounting from GPP after "
            f"{ALLOCATION_FETCH_ATTEMPTS} attempts: {last_error}"
        )

    data = payload.model_dump(by_alias=True).get("observations", {})
    matches = data.get("matches", []) or []

    template = next((m for m in matches if m.get("id") == observation_id), None)
    if template is None:
        raise TriggerFailed(
            f"Template observation {observation_id} was not found in program "
            f"{program_id}. It may have been deleted."
        )

    band = template.get("scienceBand")
    program = template.get("program") or {}

    allocated = sum(
        float(entry.get("duration", {}).get("hours") or 0.0)
        for entry in (program.get("allocations") or [])
        if band is None or entry.get("scienceBand") == band
    )
    used = sum(
        float(
            (entry.get("time") or {}).get("program", {}).get("hours") or 0.0
        )
        for entry in (program.get("timeCharge") or [])
        if band is None or entry.get("band") == band
    )
    return band, allocated, used


async def _check_allocation(client, subscription, record) -> None:
    """Refuse if the template's science band has no time left.

    Parameters
    ----------
    client : `gpp_client.GPPClient`
        An authenticated client.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription triggering.
    record : `goats_tom.models.GeminiTriggerRecord`
        This attempt's record. Unused for storage now that no per-observation
        cost is known; kept in the signature so callers need not change if a
        cost ever becomes available.

    Raises
    ------
    TriggerSkipped
        If the band's granted time is fully used.
    TriggerFailed
        If the accounting could not be read.

    Notes
    -----
    Checks remaining time in the band, not whether this particular
    observation fits: GPP does not compute a cost for an unexecuted
    observation, so that question has no answer here. The trigger cap
    (`AntaresStreamSubscription.max_triggers`) is what bounds how far past a
    nearly-exhausted band automatic triggering can go.

    Zero allocated means no time was granted in that band, so triggering is
    refused outright -- there is nothing to spend. An earlier version let this
    through on the grounds that zero might merely mean "not recorded", and
    leaned on the trigger cap instead. That was the wrong default for
    something that consumes real telescope time: reading an ambiguous value
    permissively is only safe when being wrong is cheap, and here it is not.
    """
    band, allocated, used = await _fetch_band_time(
        client, subscription.gpp_program_id, subscription.gpp_observation_id
    )

    if allocated <= 0:
        raise TriggerSkipped(
            f"The programme has no time granted in band {band}, so there is "
            f"nothing to observe with."
        )

    if used >= allocated:
        raise TriggerSkipped(
            f"No time left in band {band}: {used:.2f} h of {allocated:.2f} h "
            f"already used."
        )


def trigger_gemini_observation(
    subscription, locus_id: str, target, run_number: int = 0
) -> object:
    """Create a Gemini observation for one locus, if the guards allow it.

    Parameters
    ----------
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription whose template and limits apply.
    locus_id : str
        The ANTARES locus prompting the trigger.
    target : `tom_targets.models.Target`
        The saved GOATS target to point the new observation at.

    Returns
    -------
    `goats_tom.models.GeminiTriggerRecord`
        The record, in its final state.

    Notes
    -----
    Never raises. Every outcome is recorded on the returned row instead,
    because this runs per alert in a background task where an exception would
    only be logged and lost -- and because "why did nothing happen?" needs a
    durable answer the PI can read on the dashboard.

    The order is deliberate: reserve the row, check the cap, check the
    allocation, then create. Everything cheap and reversible happens before
    anything is created in GPP.
    """
    from goats_tom.models import GeminiTriggerRecord  # noqa: PLC0415

    try:
        record = _reserve_record(subscription, locus_id, run_number)
    except TriggerSkipped as exc:
        logger.info("Not triggering for %s: %s", locus_id, exc)
        return None

    def _finish(status: str, detail: str = "", **fields) -> object:
        record.status = status
        record.detail = detail
        for key, value in fields.items():
            setattr(record, key, value)
        record.save()
        return record

    owner = subscription.owner
    if owner is None or not hasattr(owner, "gpplogin"):
        return _finish(
            GeminiTriggerRecord.STATUS_SKIPPED,
            "The subscription owner has no GPP credentials stored.",
        )

    if not (subscription.gpp_program_id and subscription.gpp_observation_id):
        return _finish(
            GeminiTriggerRecord.STATUS_SKIPPED,
            "No GPP template observation is configured for this subscription.",
        )

    try:
        _check_cap(subscription, record)
    except TriggerSkipped as exc:
        return _finish(GeminiTriggerRecord.STATUS_SKIPPED, str(exc))

    from asgiref.sync import async_to_sync  # noqa: PLC0415
    from gpp_client import GPPClient  # noqa: PLC0415

    from goats_tom.gpp_observation_builder import (  # noqa: PLC0415
        build_source_profile,
        clone_observation_for_target,
    )
    from goats_tom.models import AntaresLocus  # noqa: PLC0415

    # Every query this attempt needs runs here, before the event loop opens.
    # Django's ORM raises `SynchronousOnlyOperation` in async context, so only
    # plain values cross into the coroutine below.
    #
    # Brightness comes from the alert that prompted this trigger, not from the
    # template: the template describes whichever object it was built around,
    # which is not the one being observed.
    locus_row = AntaresLocus.objects.filter(
        subscription=subscription, locus_id=locus_id
    ).first()
    source_profile = build_source_profile(
        getattr(locus_row, "latest_alert_magnitude", None),
        getattr(locus_row, "latest_alert_passband", None),
    )
    overrides = (
        _apply_locus_url(subscription.gpp_observation_overrides or {}, locus_id)
        or None
    )
    token = owner.gpplogin.token
    program_id = subscription.gpp_program_id
    template_observation_id = subscription.gpp_observation_id
    workflow_state = subscription.gpp_workflow_state or None
    target_overrides = subscription.gpp_target_overrides or None
    template_target_id = subscription.gpp_target_id or ""
    instrument = subscription.gpp_instrument or ""

    # Filled the moment anything exists in GPP, so a failure afterwards can
    # still be recorded against what was created -- which is what decides
    # whether the attempt counts against the cap. A plain dict, not a database
    # write: the hook runs inside the event loop, where the ORM is unavailable.
    created: dict[str, str] = {}

    def _note_created(target_id=None, observation_id=None) -> None:
        if target_id:
            created["target_id"] = target_id
        if observation_id:
            created["observation_id"] = observation_id

    async def _run() -> dict:
        """Every GPP call for this attempt, in one event loop.

        One client, one loop, one `async_to_sync` -- around all of it, not
        around each call. Wrapping the calls individually is what broke
        triggering outright: `async_to_sync` opens a loop and closes it on
        return, so the second call found the client's connection pool bound to
        a dead loop and raised ``Event loop is closed`` every time.
        """
        client = GPPClient(token=token)
        try:
            await _check_allocation(client, subscription, record)

            # Past this point something may exist in GPP, so nothing is
            # retried.
            return await clone_observation_for_target(
                client=client,
                program_id=program_id,
                template_observation_id=template_observation_id,
                target=target,
                overrides=overrides,
                source_profile=source_profile,
                workflow_state=workflow_state,
                on_created=_note_created,
                target_overrides=target_overrides,
                template_target_id=template_target_id,
            )
        finally:
            await client.close()

    try:
        result = async_to_sync(_run)()
    except TriggerSkipped as exc:
        return _finish(GeminiTriggerRecord.STATUS_SKIPPED, str(exc))
    except TriggerFailed as exc:
        # Raised only by the allocation read, before anything is created.
        return _finish(GeminiTriggerRecord.STATUS_FAILED, str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Gemini trigger failed for locus %s on subscription %s.",
            locus_id,
            subscription.pk,
        )
        # Says what actually happened rather than warning about every
        # possibility. The old text told the PI to go and check Explore after
        # any failure, including ones that never reached GPP at all.
        observation_id = created.get("observation_id", "")
        target_id = created.get("target_id", "")
        # GPP's messages usually end in a full stop of their own, and blindly
        # appending produced "...on target creation.. Nothing was created".
        exc = str(exc).strip().rstrip(".")
        if observation_id:
            detail = (
                f"{exc}. Observation {observation_id} was created before this "
                f"error and counts against the trigger limit; check its state "
                f"in Explore."
            )
        elif target_id:
            detail = (
                f"{exc}. A target was created in the programme but no "
                f"observation, so no telescope time was committed."
            )
        else:
            detail = f"{exc}. Nothing was created in GPP."
        return _finish(
            GeminiTriggerRecord.STATUS_FAILED,
            detail,
            gpp_observation_id=observation_id,
            gpp_target_id=target_id,
        )

    logger.info(
        "Triggered Gemini observation %s for locus %s (subscription %s).",
        result.get("observation_id"),
        locus_id,
        subscription.pk,
    )
    # Record it in GOATS, the way "Create and Save in GOATS" does. Without
    # this the observation existed only in GPP: nothing appeared against the
    # target, and none of the downstream machinery that watches observation
    # records ever saw it.
    observation_record = _record_observation_in_goats(
        owner=owner,
        target=target,
        instrument=instrument,
        observation=result.get("observation"),
    )

    # No detail on success. The dashboard shows the observation's reference
    # and links to it, which is everything a PI can act on; a sentence saying
    # it worked only competes with the rows that failed. The previous text
    # also interpolated the workflow-state *object* GPP returned, so the
    # column filled with `<ObservationWorkflowState.DEFINED: 'DEFINED'>
    # valid_transitions=[...]` -- a Python repr in a user-facing table.
    return _finish(
        GeminiTriggerRecord.STATUS_SUCCESS,
        "",
        gpp_observation_id=result.get("observation_id") or "",
        gpp_target_id=result.get("target_id") or "",
        observation_record=observation_record,
    )


def _record_observation_in_goats(owner, target, instrument, observation) -> str:
    """Save a created GPP observation as a GOATS `ObservationRecord`.

    Parameters
    ----------
    owner : `django.contrib.auth.models.User`
        The PI the record is created as. There is no request in a worker, so
        the acting user is taken from the subscription.
    target : `tom_targets.models.Target`
        The target to attach the record to.
    instrument : str
        The template's instrument, stored when the template was applied.
    observation : dict or None
        The observation as GPP returned it.

    Returns
    -------
    `tom_observations.models.ObservationRecord` or None
        The record, when one was created or already existed.

    Notes
    -----
    Mirrors `goats_tom.api_views.gpp.observations
    .GPPObservationViewSet._create_goats_observation`, including posting
    through the TOM viewset rather than writing the row directly, so both
    paths produce records of the same shape.

    Never raises. The observation exists in GPP by this point, and failing the
    whole trigger over the bookkeeping would misreport a real observation as
    not having happened.
    """
    if not observation or not instrument:
        logger.error(
            "Cannot record observation in GOATS for target %s: %s.",
            getattr(target, "name", None),
            "no observation returned" if not observation else "no instrument",
        )
        return None

    try:
        from rest_framework.test import APIRequestFactory  # noqa: PLC0415
        from tom_observations.api_views import (  # noqa: PLC0415
            ObservationRecordViewSet,
        )
        from tom_observations.models import ObservationRecord  # noqa: PLC0415

        facility = "GEM"
        observation_id = (observation.get("reference") or {}).get("label")
        existing = ObservationRecord.objects.filter(
            target_id=target.id,
            facility=facility,
            observation_id=observation_id,
        ).first()
        if existing is not None:
            return existing

        payload = {
            "target_id": target.id,
            "facility": facility,
            "observation_type": instrument,
            "observing_parameters": {
                **observation,
                "target_id": target.id,
                "facility": facility,
            },
        }
        request = APIRequestFactory().post(
            "/api/observations/", payload, format="json"
        )
        request.user = owner
        response = ObservationRecordViewSet.as_view({"post": "create"})(request)
        if response.status_code >= 400:
            logger.error(
                "Could not record observation %s in GOATS: %s",
                observation_id,
                getattr(response, "data", response.status_code),
            )
            return None

        record = ObservationRecord.objects.filter(
            target_id=target.id,
            facility=facility,
            observation_id=observation_id,
        ).first()
        if record is not None:
            # The API path assigns no per-object permissions, so without this
            # the observation is invisible to everyone including the PI who
            # triggered it -- see `goats_tom.permissions`.
            grant_observation_permissions(record, owner)
        return record
    except Exception:
        logger.exception(
            "Could not record the created observation in GOATS for target %s.",
            getattr(target, "name", None),
        )
        return None
