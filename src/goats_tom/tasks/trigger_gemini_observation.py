"""Background task that triggers a Gemini observation for one locus.

Run as a task rather than inline in the ANTARES consume loop for two reasons.
Creating an observation means several round trips to GPP -- reading the
allocation, creating a target, cloning, then polling until the workflow state
takes -- which would stall ingestion for every alert. And a GPP outage would
stop the stream entirely, so an unrelated service being down would cost the
dashboard as well as the triggering.
"""

__all__ = ["trigger_gemini_observation_task"]

import logging

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=0)
def trigger_gemini_observation_task(subscription_id: int, locus_id: str) -> None:
    """Trigger a Gemini observation for one saved locus.

    Parameters
    ----------
    subscription_id : int
        The subscription whose template and limits apply.
    locus_id : str
        The locus to observe. Looked up here rather than passed as an object,
        since only primitives survive the message broker.

    Notes
    -----
    ``max_retries=0``, matching every other GOATS actor and required here
    rather than merely conventional: a retry re-runs the whole task, and if the
    first run created an observation but failed afterwards, the second would
    create another and charge the allocation twice.

    Safe retries are handled inside the trigger itself, which repeats only the
    allocation lookup -- a read, before anything exists to duplicate. See
    `goats_tom.gemini_trigger`.

    Never raises. Outcomes are recorded on `GeminiTriggerRecord` so the PI can
    see on the dashboard why a locus was or was not observed; an exception here
    would only reach the worker log.
    """
    from tom_targets.models import Target

    from goats_tom.gemini_trigger import trigger_gemini_observation
    from goats_tom.models import AntaresStreamSubscription

    subscription = (
        AntaresStreamSubscription.objects.select_related("owner")
        .filter(pk=subscription_id)
        .first()
    )
    if subscription is None:
        logger.warning(
            "Subscription %s no longer exists; not triggering for locus %s.",
            subscription_id,
            locus_id,
        )
        return

    if not subscription.trigger_gemini_observations:
        # Turned off between the alert arriving and this task running.
        logger.info(
            "Gemini triggering is disabled for subscription %s; skipping "
            "locus %s.",
            subscription_id,
            locus_id,
        )
        return

    target = Target.objects.filter(name=locus_id).first()
    if target is None:
        target = Target.objects.filter(aliases__name=locus_id).first()
    if target is None:
        logger.warning(
            "No saved target for locus %s; not triggering. The save may have "
            "failed.",
            locus_id,
        )
        return

    try:
        trigger_gemini_observation(subscription, locus_id, target)
    except Exception:  # noqa: BLE001
        # `trigger_gemini_observation` records its own outcomes, so reaching
        # here means something failed outside that handling. Logged rather
        # than raised: the consumer must not be affected by it.
        logger.exception(
            "Unexpected error while triggering Gemini for locus %s on "
            "subscription %s.",
            locus_id,
            subscription_id,
        )
