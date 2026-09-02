"""Supervising GOA downloads and DRAGONS reductions running on Data Lab.

Each cycle, for every job still in flight:

1. **Poll** the runner's `status.json` and copy what it reports.
2. **Stream** new NDJSON log records to the UI, so a PI watching a reduction
   sees what they would see locally.
3. **Collect**, once a job reports finished: create `DataProduct` rows for a
   download, or attach outputs for a reduction.
4. **Reap** jobs whose heartbeat has gone stale.

Deliberately separate from `supervise_remote_jobs`, which serves the ANTARES
stream. See *Keep ANTARES out of Phases 3 and 4* in ``STATUS.md``.

**What a runner reports is not trusted about content.** It reports filenames
and sizes; headers are read here, from storage, with the same astrodata code
the local path uses. A runner that lied about a header would otherwise write
a false `DataProductMetadata` row that nothing later would catch.
"""

__all__ = ["supervise_datalab_jobs"]

import logging

import dramatiq
from django.utils import timezone

from goats_tom.astro_data_lab.headless import DataLabHeadlessClient, HeadlessConfig
from goats_tom.models import DataLabJob

logger = logging.getLogger(__name__)

#: Silence after which a job is presumed dead.
#:
#: Runners write progress every 5 seconds, so this is generous. It has to be:
#: a large tar member can take a long time to upload, and reaping a job that
#: is working is worse than leaving a dead one for another minute.
STALE_AFTER_SECONDS = 300.0

#: Most log records republished per job per cycle.
#:
#: A reduction can emit thousands of lines in a burst. Without a cap one
#: chatty job would monopolise the cycle and delay every other PI's.
MAX_LOG_RECORDS = 500


@dramatiq.actor(max_retries=0, time_limit=600_000)
def supervise_datalab_jobs() -> None:
    """Advance every in-flight Data Lab job by one cycle."""
    jobs = DataLabJob.objects.filter(
        status__in=(DataLabJob.Status.PENDING, DataLabJob.Status.RUNNING)
    ).select_related("user", "observation_record", "dragons_run")

    for job in jobs:
        try:
            _supervise_one(job)
        except Exception:
            # One PI's broken account must not stop the cycle for everyone
            # else. The job stays active and is retried next cycle, or goes
            # stale and is reaped.
            logger.exception("Unhandled error supervising Data Lab job %s.", job.pk)


def _client_for(job: DataLabJob) -> DataLabHeadlessClient:
    """Return a headless client authenticated as `job`'s owner."""
    credentials = job.user.astrodatalablogin
    return DataLabHeadlessClient(
        username=credentials.username,
        password=credentials.password,
        config=HeadlessConfig(),
    )


def _supervise_one(job: DataLabJob) -> None:
    """Run one cycle for a single job."""
    client = _client_for(job)
    try:
        _stream_logs(client, job)
        status = client.job_status(job.job_id)
        _apply_status(job, status)

        if job.status == DataLabJob.Status.FINISHED:
            _collect(job, status)
    finally:
        client.close()

    if job.is_stale(STALE_AFTER_SECONDS):
        _reap(job)


def _apply_status(job: DataLabJob, status: dict) -> None:
    """Copy what the runner reported onto `job`.

    Notes
    -----
    `last_heartbeat` advances only when the status file *changes*, not on
    every poll. A runner that wedges keeps its status file intact, so
    treating a successful read as a heartbeat would make a hung job look
    healthy forever -- the failure mode `RemoteJob` documents and this
    repeats deliberately.
    """
    state = str(status.get("state", "")).lower()
    fields = []

    seen = int(status.get("seen", job.files_seen) or 0)
    kept = int(status.get("kept", job.files_kept) or 0)
    if (seen, kept) != (job.files_seen, job.files_kept):
        job.files_seen, job.files_kept = seen, kept
        job.last_heartbeat = timezone.now()
        fields += ["files_seen", "files_kept", "last_heartbeat"]

    if state == "finished" and job.status != DataLabJob.Status.FINISHED:
        job.status = DataLabJob.Status.FINISHED
        job.finished_at = timezone.now()
        job.last_heartbeat = timezone.now()
        fields += ["status", "finished_at", "last_heartbeat"]
    elif state == "failed" and job.status != DataLabJob.Status.FAILED:
        job.status = DataLabJob.Status.FAILED
        job.finished_at = timezone.now()
        job.error = str(status.get("reason", ""))[:2000]
        fields += ["status", "finished_at", "error"]
    elif state == "running" and job.status == DataLabJob.Status.PENDING:
        job.status = DataLabJob.Status.RUNNING
        fields.append("status")

    if fields:
        job.save(update_fields=sorted(set(fields)))


def _stream_logs(client: DataLabHeadlessClient, job: DataLabJob) -> None:
    """Republish new NDJSON records to the UI.

    Notes
    -----
    Uses `tail_ndjson`, which was written for this and had no caller until
    now. `log_offset` is persisted so polling resumes rather than restarting,
    and `tail_ndjson` stops at the first line that does not parse -- a read
    landing mid-write sees a truncated final line, and counting it as
    consumed would skip a record about to become valid.

    This is what replaces `DRAGONSHandler` for remote runs. That handler is a
    `logging.Handler` in the reduction's own process, pushing to a Channels
    group; no such process exists on the VM when the reduction is remote.
    """
    path = f"{HeadlessConfig().job_root}/{job.job_id}/events.ndjson"
    try:
        records, offset = client.tail_ndjson(path, job.log_offset)
    except Exception:
        # Logs are a nicety; losing them must never fail a job.
        logger.debug("Could not tail logs for %s.", job.job_id, exc_info=True)
        return

    if not records:
        return

    for record in records[:MAX_LOG_RECORDS]:
        _publish(job, record)

    job.log_offset = offset
    job.last_heartbeat = timezone.now()
    job.save(update_fields=["log_offset", "last_heartbeat"])


def _publish(job: DataLabJob, record: dict) -> None:
    """Send one log record to the job's UI channel.

    Notes
    -----
    Best-effort. A closed websocket or an unconfigured channel layer must not
    fail a reduction that is otherwise fine.
    """
    try:
        from asgiref.sync import async_to_sync  # noqa: PLC0415
        from channels.layers import get_channel_layer  # noqa: PLC0415

        layer = get_channel_layer()
        if layer is None:
            return
        group = (
            f"dragons_run_{job.dragons_run_id}"
            if job.kind == DataLabJob.Kind.REDUCTION
            else f"download_{job.observation_record_id}"
        )
        async_to_sync(layer.group_send)(
            group, {"type": "job.log", "payload": record}
        )
    except Exception:
        logger.debug("Could not publish log record for %s.", job.job_id, exc_info=True)


def _collect(job: DataLabJob, status: dict) -> None:
    """Record what a finished job produced.

    Notes
    -----
    Downloads create `DataProduct` rows pointing at the names the runner
    wrote. Reductions attach their outputs to the run.

    **Headers are read here, not reported.** The runner supplies names and
    sizes; this side opens each file through `goats_tom.storage` and builds
    metadata with the same astrodata code the local path uses. Slower than
    trusting a report, and there is nothing new to trust.
    """
    if job.kind == DataLabJob.Kind.DOWNLOAD:
        _collect_download(job, status)
    else:
        _collect_reduction(job, status)


def _collect_download(job: DataLabJob, status: dict) -> None:
    """Create `DataProduct` rows for the files a download wrote."""
    from tom_dataproducts.models import DataProduct  # noqa: PLC0415

    from goats_tom.permissions import grant_dataproduct_permissions  # noqa: PLC0415

    record = job.observation_record
    credentials = job.user.astrodatalablogin
    prefix = (
        f"users/{credentials.username}/goats/"
        f"{record.target.name}/{record.facility}/{record.observation_id}"
    )

    created = 0
    for entry in status.get("files", []):
        name = f"{prefix}/{entry['name']}"
        if DataProduct.objects.filter(data=name).exists():
            continue
        product = DataProduct.objects.create(
            target=record.target,
            observation_record=record,
            product_id=name,
            data=name,
        )
        # Without this the file exists and is invisible to everyone including
        # the PI who downloaded it -- the failure mode recorded throughout
        # `goats_tom.permissions`.
        grant_dataproduct_permissions(product, job.user)
        created += 1

    logger.info("Collected %s new data products from download %s.", created, job.job_id)


def _collect_reduction(job: DataLabJob, status: dict) -> None:
    """Record when each of a reduction's outputs was written.

    Notes
    -----
    **Creates no `DataProduct` rows, deliberately.** The local reduction
    records nothing either: `run_dragons_reduce` calls `runr()`, marks the
    run done and stops. Outputs are discovered afterwards by
    `DRAGONSRun.get_processed_files`, and the PI chooses which become data
    products from the processed-files panel. Promoting them here would fill
    Manage Data with intermediates nobody asked for and make remote
    reductions behave unlike local ones.

    What does need recording is **when each file was written**, because
    VOSpace cannot answer that later and the panel uses it to mark a file
    "updated" when a reduction has rewritten one the PI already saved.

    Merged rather than replaced. A run is not one reduction -- a recipe can
    be rerun repeatedly within it -- so entries this job did not touch keep
    the time they already had. Replacing the map would restamp every file
    with the newest job's outputs and lose the history of the earlier ones.
    """
    run = job.dragons_run
    if run is None:
        return

    outputs = status.get("outputs", [])
    prefix = run.get_output_prefix()

    written = dict(run.output_written_at or {})
    for entry in outputs:
        name = entry.get("name")
        timestamp = entry.get("written_at")
        if name and timestamp:
            written[f"{prefix}/{name}"] = timestamp

    if written != run.output_written_at:
        run.output_written_at = written
        run.save(update_fields=["output_written_at"])

    logger.info(
        "Reduction %s produced %s output(s) for run %s.",
        job.job_id,
        len(outputs),
        run.pk,
    )


def _reap(job: DataLabJob) -> None:
    """Mark a job that has gone quiet as lost.

    Notes
    -----
    No attempt is made to kill the remote process. There is no process API
    once detached, and anything it writes afterwards lands in a VOSpace
    directory whose job row is already closed -- visible, harmless, and
    preferable to a kill that cannot be relied on anyway.
    """
    job.status = DataLabJob.Status.LOST
    job.finished_at = timezone.now()
    job.error = (
        f"No progress reported for over {int(STALE_AFTER_SECONDS)}s. The runner "
        "may have been culled, or the notebook server stopped."
    )
    job.save(update_fields=["status", "finished_at", "error"])
    logger.warning("Reaped stale Data Lab job %s.", job.job_id)
