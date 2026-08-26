"""Periodic supervision of Astro Data Lab stream jobs.

Turns the one-off launch validated by ``roundtrip_one_pi.py`` into something
that manages itself for many PIs: launch a window, watch it, pull its results
into `AntaresLocus`, reap it, launch the next.

**Inert unless ``GOATS_STREAM_EXECUTOR`` is ``"datalab"``.** On a desktop
install this returns immediately, before importing anything from the remote
path, so the optional ``goats[server]`` dependencies are never needed. That
is the hard invariant of this work, and it is why the imports below are
function-local rather than module-level -- this module is imported by
`goats_tom.tasks`, which every install loads.

Each cycle, per subscription:

1. **Poll** active jobs and copy what they report into `RemoteJob`.
2. **Collect** rows from the PI's MyDB into `AntaresLocus`, then reclaim the
   space -- strictly in that order.
3. **Reap** jobs whose heartbeat has gone stale.
4. **Launch** a fresh window if none is active.

Ordering matters in step 2. The runner has already advanced its Kafka offsets
past those alerts, so dropping the drain table before the rows are committed
loses them for good. Collection therefore always runs before reaping, even
for a job that has failed -- a failed window may still have written loci
before it died.
"""

__all__ = ["supervise_remote_jobs"]

import logging
from datetime import datetime
from datetime import timezone as dt_timezone

import dramatiq
from django.utils import timezone

from goats_scheduler.scheduling import cron
from goats_tom.models import AntaresStreamSubscription, RemoteJob
from goats_tom.tasks.ingest_antares_stream import (
    LocusCapReached,
    strip_topic_prefix,
    upsert_locus_row,
)

logger = logging.getLogger(__name__)

#: Seconds without a heartbeat before an active job is presumed dead. Must
#: exceed the runner's own deadline, or a job that is merely finishing gets
#: reaped as if it had crashed.
STALE_AFTER_SECONDS = 20 * 60

#: How often the whole cycle runs is set by the `@cron` below: every 15
#: seconds, so a locus written to MyDB reaches the dashboard within that
#: rather than within a minute. Collection is the latency-sensitive half;
#: launching is not, but running both together avoids a second scheduled task
#: and the launch path is cheap when a job is already active -- one indexed
#: query per subscription. `coalesce` and `max_instances=1` mean a cycle that
#: overruns simply skips the next tick instead of piling up.

#: Seconds between launches within one cycle. 300 PIs spawning notebook
#: servers simultaneously would be a thundering herd against the Hub; a small
#: stagger costs nothing when windows are ten minutes long.
LAUNCH_STAGGER_SECONDS = 2.0

#: Most rows accepted from one subscription per cycle. A handler that returns
#: `True` for everything sends the firehose, and the VM is the shared resource
#: that must not fall over because of it.
MAX_ROWS_PER_CYCLE = 5000


@cron(second="*/15")
@dramatiq.actor(max_retries=0)
def supervise_remote_jobs() -> None:
    """Advance every `datalab`-mode subscription by one supervision cycle."""
    from goats_tom.executors import DATALAB, resolve_executor_name  # noqa: PLC0415

    if resolve_executor_name() != DATALAB:
        # The overwhelmingly common case. Nothing from the remote path has
        # been imported at this point, and nothing will be.
        return

    from goats_tom.astro_data_lab.headless import HeadlessError  # noqa: PLC0415
    from goats_tom.executors import get_executor  # noqa: PLC0415

    from django.db.models import Q  # noqa: PLC0415

    executor = get_executor()
    # Subscriptions the user wants running, *plus* any with a job still
    # active. The second half matters on its own: if `is_running` is ever
    # cleared while a remote window is in flight, selecting on it alone would
    # orphan that job -- never polled, never collected, never reaped, while it
    # keeps consuming the PI's quota.
    subscriptions = AntaresStreamSubscription.objects.filter(
        Q(is_running=True)
        | Q(
            remote_jobs__status__in=(
                RemoteJob.Status.PENDING,
                RemoteJob.Status.RUNNING,
            )
        )
    ).distinct()

    for index, subscription in enumerate(subscriptions):
        try:
            _supervise_one(executor, subscription, index)
        except HeadlessError as exc:
            # One PI's missing credentials or unreachable server must not
            # stall the other 299.
            logger.warning(
                "Skipping subscription %s this cycle: %s", subscription.pk, exc
            )
        except Exception:
            logger.exception(
                "Unhandled error supervising subscription %s.", subscription.pk
            )


def _supervise_one(executor, subscription, index: int) -> None:
    """Run one cycle for a single subscription."""
    import time  # noqa: PLC0415

    client = _client_for(executor, subscription)
    try:
        _poll_active_jobs(client, subscription)
        _collect(executor, subscription)
        _reap_stale(client, subscription)
    finally:
        client.close()

    if RemoteJob.objects.filter(
        subscription=subscription,
        status__in=(RemoteJob.Status.PENDING, RemoteJob.Status.RUNNING),
    ).exists():
        return

    # Re-read: _collect may have just cleared this at the cap.
    subscription.refresh_from_db(fields=["is_running"])
    if not subscription.is_running:
        return

    if index:
        time.sleep(LAUNCH_STAGGER_SECONDS)
    executor.start(subscription, subscription.generation)


def _client_for(executor, subscription):
    """Build one notebook-server client for this cycle.

    Notes
    -----
    Shared across polling and reaping rather than built per step: each
    construction is an HTTP session, and at 300 subscriptions a minute the
    difference is real.
    """
    from goats_tom.astro_data_lab.headless import (  # noqa: PLC0415
        DataLabHeadlessClient,
    )

    credentials = executor._credentials(subscription)
    return DataLabHeadlessClient(
        credentials["datalab_username"],
        credentials["jupyter_token"],
        config=executor._config(),
    )


def _poll_active_jobs(client, subscription) -> None:
    """Copy each active job's self-reported status onto its `RemoteJob` row.

    Notes
    -----
    `status` is what the runner last *wrote*, not proof it is alive -- a
    detached process that dies abruptly leaves ``running`` behind forever.
    `last_heartbeat` is only advanced when the reported status actually
    changes, which is what makes staleness detectable: a frozen runner keeps
    reporting the same thing, so its heartbeat stops moving even though the
    file is still readable.
    """
    active = RemoteJob.objects.filter(
        subscription=subscription,
        status__in=(RemoteJob.Status.PENDING, RemoteJob.Status.RUNNING),
    )
    for job in active:
        try:
            status = client.job_status(job.job_id)
        except Exception:
            logger.warning(
                "Could not read status for job %s.", job.job_id, exc_info=True
            )
            continue

        # Liveness comes from the runner's own timestamp, not from the
        # values changing.
        #
        # The runner rewrites `status.json` on a timer, so `ts` advances even
        # through stretches where no locus arrives. Deriving liveness from
        # `seen`/`kept` instead would mark a healthy job on a quiet topic as
        # stale -- it reports the same numbers every time precisely because
        # it is working correctly and there is nothing to report.
        #
        # `ts` is Data Lab's clock and `is_stale` compares against the VM's,
        # so this carries whatever skew exists between them. Both are NTP
        # synced and the threshold is twenty minutes, so seconds of drift are
        # immaterial -- and the alternative, storing the last-seen timestamp
        # to compare like with like, needs a column for no practical gain.
        reported_at = status.get("ts")
        if reported_at:
            try:
                job.last_heartbeat = datetime.fromtimestamp(
                    float(reported_at), tz=dt_timezone.utc
                )
            except (TypeError, ValueError, OSError):
                job.last_heartbeat = timezone.now()
        else:
            job.last_heartbeat = timezone.now()

        job.loci_seen = int(status.get("seen") or 0)
        job.loci_kept = int(status.get("kept") or 0)

        state = str(status.get("state") or "")
        terminal = state in (RemoteJob.Status.FINISHED, RemoteJob.Status.FAILED)
        if terminal:
            job.status = state
            job.finished_at = timezone.now()
            if state == RemoteJob.Status.FAILED:
                job.error = str(status.get("reason") or "")[:2000]
                if status.get("unhealthy"):
                    _mark_unhealthy(subscription, status)
        job.save()

        # Directory cleanup is not done here. It rides on the next launch's
        # kernel instead -- see `DataLabExecutor.start` -- because a
        # cleanup-only kernel stages a notebook of its own and leaves an
        # `.ipynb_checkpoints` behind, creating litter while clearing it.


def _mark_unhealthy(subscription, status) -> None:
    """Surface a handler failure on the subscription itself.

    Notes
    -----
    Written to the same `last_handler_warning` field the local path uses, so
    the dashboard banner works identically in both modes and a PI can clear
    it by fixing their handler -- rather than needing an administrator, which
    would not scale to 300 users whose handlers will break routinely.
    """
    reason = status.get("reason") or "handler raised"
    locus_id = status.get("locus_id")
    detail = f"{reason} on locus {locus_id}" if locus_id else reason
    subscription.last_handler_warning = (
        f"Your locus handler failed on Data Lab: {detail}. The window was "
        "stopped and those alerts will be retried once the handler is fixed."
    )
    subscription.last_handler_warning_at = timezone.now()
    subscription.save(
        update_fields=["last_handler_warning", "last_handler_warning_at"]
    )


def _collect(executor, subscription) -> None:
    """Pull this subscription's MyDB rows into `AntaresLocus`.

    Notes
    -----
    Reclaims the PI's MyDB space only after every row has been committed --
    the runner's Kafka offsets have already moved past these alerts, so an
    early drop loses them permanently.

    Every field arriving here is a **claim, not a fact**. The runner and its
    job spec are staged in a directory the PI can write to, so a PI could
    edit either and emit rows naming another subscription. The subscription
    used below is the one this cycle authenticated as, never the row's, and
    `generation` is compared against the value held locally rather than
    adopted.
    """
    rows = executor.collect(subscription)
    if not rows:
        # Drop the drain table even though it is empty.
        #
        # `collect()` has already rotated the live table aside, so returning
        # here without dropping strands it. The next cycle then finds a
        # pre-existing drain table, hands that back *instead of rotating
        # again*, finds it empty too, and returns -- so the live table is
        # never rotated again and loci accumulate on Data Lab that the VM can
        # never collect. An empty window is completely normal on a quiet
        # topic, which is what made this deadlock easy to reach.
        executor.finish_collect(subscription)
        return

    if len(rows) > MAX_ROWS_PER_CYCLE:
        logger.warning(
            "Subscription %s returned %d rows; accepting the oldest %d this "
            "cycle. A handler that filters nothing will do this repeatedly.",
            subscription.pk, len(rows), MAX_ROWS_PER_CYCLE,
        )
        rows = rows[:MAX_ROWS_PER_CYCLE]

    accepted = rejected = 0
    capped = False
    for row in rows:
        locus_id = (row.get("locus_id") or "").strip()
        if not locus_id:
            rejected += 1
            continue
        # Fencing, and tamper rejection, in one check.
        if str(row.get("generation") or "") != str(subscription.generation):
            rejected += 1
            continue
        if str(row.get("subscription_id") or "") != str(subscription.pk):
            logger.warning(
                "Discarding row from subscription %s claiming subscription %r.",
                subscription.pk, row.get("subscription_id"),
            )
            rejected += 1
            continue
        try:
            upsert_locus_row(subscription.pk, locus_id, _field_updates(row))
        except LocusCapReached:
            # The subscription is full. Everything already read stays read --
            # the drain table is dropped below regardless, because those rows
            # are past the runner's committed Kafka offsets and cannot be
            # fetched again. Refusing them is the intended outcome, not a
            # loss.
            capped = True
            break
        accepted += 1

    # Only after every accepted row is committed.
    executor.finish_collect(subscription)
    logger.info(
        "Collected %d loci for subscription %s (%d rejected%s).",
        accepted, subscription.pk, rejected, ", cap reached" if capped else "",
    )
    if capped:
        _stop_at_cap(subscription)


def _stop_at_cap(subscription) -> None:
    """Stop a subscription that has reached `max_loci`.

    Notes
    -----
    Clearing `is_running` is what actually halts the cycle: no further windows
    are launched, and the running one ends at its own deadline. Any loci it
    writes in the meantime are simply refused on the next collection.

    The user asked for this, so it is reported through the same banner as a
    handler warning rather than as a failure -- and the subscription can be
    restarted from the UI once they raise the limit or clear the dashboard.
    """
    subscription.is_running = False
    subscription.last_handler_warning = (
        f"Ingestion stopped: the dashboard has reached its limit of "
        f"{subscription.max_loci} loci. Raise or clear the limit, or clear "
        "the dashboard, then start ingestion again."
    )
    subscription.last_handler_warning_at = timezone.now()
    subscription.save(
        update_fields=[
            "is_running", "last_handler_warning", "last_handler_warning_at"
        ]
    )
    logger.info("Subscription %s stopped at its loci cap.", subscription.pk)


def _field_updates(row) -> dict:
    """Map one MyDB row onto `AntaresLocus` columns.

    Notes
    -----
    The remote counterpart of the mapping `_upsert_locus` builds from a live
    `Locus`; both hand the result to the same `upsert_locus_row`, so the two
    paths cannot write different columns.

    Everything arrives as a string, because the values came back through CSV.
    Numeric fields are coerced individually and left `None` when absent or
    unparseable: a missing magnitude is ordinary for a sparse alert and must
    not discard the whole row.
    """

    def number(key):
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            return None

    return {
        "ra": number("ra"),
        "dec": number("dec"),
        "latest_alert_id": row.get("latest_alert_id") or "",
        "latest_alert_mjd": number("mjd"),
        "latest_alert_magnitude": number("magnitude"),
        "latest_alert_passband": row.get("passband") or "",
        "latest_alert_topic": strip_topic_prefix(row.get("topic") or ""),
        # CSV booleans come back as PostgreSQL's "t"/"f".
        "in_tns": str(row.get("in_tns", "")).lower() in ("t", "true", "1"),
    }


def _reap_stale(client, subscription) -> None:
    """Mark active jobs whose heartbeat has aged out as lost.

    Notes
    -----
    Marked `LOST` rather than `FAILED`: the job reported nothing about why it
    stopped, and conflating that with a failure that carries a reason would
    make the two indistinguishable on the dashboard.

    No attempt is made to kill the remote process. It has no process API once
    detached, its own deadline will end it, and `generation` fencing makes
    anything it writes in the meantime unusable.
    """
    for job in RemoteJob.objects.filter(
        subscription=subscription,
        status__in=(RemoteJob.Status.PENDING, RemoteJob.Status.RUNNING),
    ):
        if not job.is_stale(STALE_AFTER_SECONDS):
            continue
        logger.warning(
            "Remote job %s has not reported for %ds; marking lost.",
            job.job_id, STALE_AFTER_SECONDS,
        )
        job.status = RemoteJob.Status.LOST
        job.finished_at = timezone.now()
        job.restart_count += 1
        job.save(update_fields=["status", "finished_at", "restart_count"])
