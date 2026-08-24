"""Executor that runs stream consumption on Astro Data Lab.

Server-deployment only. Resolved lazily by `goats_tom.executors.get_executor`
and never imported when ``GOATS_STREAM_EXECUTOR`` is unset, so the desktop
install never needs the optional ``goats[server]`` dependencies.

This is a transcription of the sequence validated end to end by
``roundtrip_one_pi.py``: stage the runner, launch it detached, let it drain a
window into the PI's MyDB, then rotate that table aside and pull the rows in.
No new mechanism is introduced here -- only the bookkeeping that a single
scripted run did by hand.
"""

__all__ = ["DataLabExecutor"]

import json
import logging
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.utils import timezone

from goats_tom.astro_data_lab.headless import (
    DataLabHeadlessClient,
    HeadlessConfig,
    HeadlessError,
)
from goats_tom.astro_data_lab.mydb import MyDBClient, loci_table_name
from goats_tom.models import RemoteJob

from .base import ExecutorHandle, StreamExecutor

logger = logging.getLogger(__name__)

RUNNER = Path(__file__).resolve().parent.parent / "remote" / "runner.py"
MYDB = Path(__file__).resolve().parent.parent / "astro_data_lab" / "mydb.py"


class DataLabExecutor(StreamExecutor):
    """Launch windowed runners on Data Lab and collect their results."""

    name = "datalab"

    def _config(self) -> HeadlessConfig:
        """Build the notebook-server config from Django settings.

        Notes
        -----
        Every value has a default, and all are read with `getattr`, so a
        `generated.py` predating this work does not raise -- the same rule
        that governs `GOATS_STREAM_EXECUTOR` itself.
        """
        return HeadlessConfig(
            base_url=getattr(
                settings, "GOATS_DATALAB_JUPYTER_URL",
                "https://gp13.datalab.noirlab.edu",
            ),
            hub_url=getattr(settings, "GOATS_DATALAB_HUB_URL", None),
            kernel_name=getattr(settings, "GOATS_DATALAB_KERNEL", "python3"),
            timeout=float(getattr(settings, "GOATS_DATALAB_TIMEOUT", 30.0)),
        )

    def _credentials(self, subscription) -> dict[str, str]:
        """Collect the PI's Data Lab and ANTARES credentials.

        Returns
        -------
        dict
            Data Lab username, a freshly minted science token, a JupyterHub
            token, and the ANTARES Kafka key/secret.

        Raises
        ------
        HeadlessError
            If a credential is missing, named individually. A PI who has
            linked Data Lab but not ANTARES should be told which, not handed
            a generic failure.

        Notes
        -----
        Two credentials are needed on the Data Lab side and they are **not
        interchangeable**: a science token for ``/auth`` and MyDB, and a
        JupyterHub token for spawning and driving the notebook server.

        `AstroDatalabLogin` stores only a username and password, so the
        science token is minted here by logging in. The JupyterHub token has
        nowhere to live yet -- it is read from an optional `jupyter_token`
        attribute, which does not exist on the model. **Adding a nullable
        `jupyter_token` field to `AstroDatalabLogin` is an outstanding
        decision**; until then `datalab` mode cannot launch, and the error
        below says so rather than failing obscurely inside the Hub API.
        """
        datalab = getattr(subscription.owner, "astrodatalablogin", None)
        kafka = getattr(subscription.owner, "antareskafkalogin", None)
        missing = []
        if not datalab:
            missing.append("Astro Data Lab login")
        if not kafka:
            missing.append("ANTARES Kafka login")
        if missing:
            raise HeadlessError(
                f"{subscription.owner} has not linked: {', '.join(missing)}."
            )

        jupyter_token = getattr(datalab, "jupyter_token", "") or ""
        if not jupyter_token:
            raise HeadlessError(
                f"{subscription.owner} has no JupyterHub token stored. This is "
                "a separate credential from the Data Lab science token and "
                "AstroDatalabLogin has no field for it yet."
            )

        return {
            "datalab_username": datalab.username,
            "datalab_token": self._science_token(datalab),
            "jupyter_token": jupyter_token,
            # ANTARES Kafka credentials are api_key/api_secret, not the
            # username/password of `UsernamePasswordLogin`.
            "kafka_key": kafka.api_key,
            "kafka_secret": kafka.api_secret,
        }

    def _science_token(self, datalab) -> str:
        """Mint a Data Lab science token from stored credentials.

        Notes
        -----
        Minted per launch rather than cached. Tokens expire, and a stale one
        fails in an especially unhelpful way: `queryClient` calls report
        ``'OK'`` regardless of what the service said, so an expired token
        looks like a silent no-op rather than an auth error.
        """
        from dl import authClient  # noqa: PLC0415 -- optional, server only

        token = authClient.login(datalab.username, datalab.password)
        if not token or "Error" in str(token):
            raise HeadlessError(
                f"Data Lab login failed for {datalab.username}: {token}"
            )
        return str(token)

    def start(self, subscription, generation: int) -> ExecutorHandle:
        """Launch one window for `subscription`.

        Notes
        -----
        The `RemoteJob` row is created **before** the launch, so a launch that
        fails partway still leaves a record. A job that exists remotely with
        no row on the VM is unreapable; the reverse is merely untidy.
        """
        credentials = self._credentials(subscription)
        table = loci_table_name()
        window = int(
            getattr(subscription, "window_minutes", None)
            or getattr(settings, "GOATS_DATALAB_WINDOW_MINUTES", 10)
        ) * 60

        job = RemoteJob.objects.create(
            subscription=subscription,
            generation=generation,
            run_number=subscription.run_number,
            datalab_username=credentials["datalab_username"],
            job_id=f"sub{subscription.pk}-gen{generation}-{timezone.now():%Y%m%d%H%M%S}",
            status=RemoteJob.Status.PENDING,
        )

        spec = {
            "subscription_id": subscription.pk,
            "generation": generation,
            "run_number": subscription.run_number,
            "window_seconds": window,
            # Comfortably past the window: the watchdog is a backstop for a
            # runner that missed its own deadline, not the primary mechanism.
            "deadline_seconds": window + 120,
            "table": table,
            "datalab_token": credentials["datalab_token"],
            "topics": list(subscription.topics or []),
            "kafka_key": credentials["kafka_key"],
            "kafka_secret": credentials["kafka_secret"],
            # The subscription's own resolved name, not one invented here.
            # It already guarantees per-subscription uniqueness by including
            # the primary key, and treats the user's `consumer_group` field as
            # a suffix whose change is the documented way to force a replay.
            # Inventing a name would silently override that.
            "consumer_group": subscription.resolved_consumer_group,
            "extra_sys_path": list(
                getattr(settings, "GOATS_DATALAB_EXTRA_SYS_PATH", [])
            ),
            "strip_kafka_options": list(
                getattr(settings, "GOATS_DATALAB_STRIP_KAFKA_OPTIONS", [])
            ),
        }

        client = DataLabHeadlessClient(
            credentials["datalab_username"],
            credentials["jupyter_token"],
            config=self._config(),
        )
        try:
            client.ensure_server()
            handle = client.launch(
                script=RUNNER.read_text(),
                args=["--spec", "job_spec.json"],
                extra_files={
                    # Staged as a sibling and imported as plain `mydb`, so
                    # Data Lab needs no goats_tom install and both sides share
                    # one file rather than a copy.
                    "mydb.py": MYDB.read_text(),
                    "handler.py": subscription.handler_code or "",
                    "job_spec.json": json.dumps(spec),
                },
                job_id=job.job_id,
            )
        except Exception as exc:
            job.status = RemoteJob.Status.FAILED
            job.error = f"launch failed: {type(exc).__name__}: {exc}"
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error", "finished_at"])
            raise
        finally:
            client.close()

        job.session_id = handle.session_id
        job.kernel_id = handle.kernel_id
        job.remote_pid = handle.pid
        job.status = RemoteJob.Status.RUNNING
        job.last_heartbeat = timezone.now()
        job.save(
            update_fields=[
                "session_id", "kernel_id", "remote_pid", "status", "last_heartbeat"
            ]
        )
        return ExecutorHandle(
            kind=self.name, remote_job_id=job.pk, detail={"job_id": job.job_id}
        )

    def stop(self, subscription) -> None:
        """Best-effort halt of `subscription`'s active remote jobs.

        Notes
        -----
        Weaker than the local abort and deliberately so. There is no process
        API for a detached runner, so this opens a fresh kernel purely to
        signal a remembered PID, and fails outright if the notebook server has
        been culled. What actually stops stale work is the runner's own
        deadline plus `generation` fencing at ingest. Never raises.
        """
        active = RemoteJob.objects.filter(
            subscription=subscription,
            status__in=(RemoteJob.Status.PENDING, RemoteJob.Status.RUNNING),
        )
        if not active.exists():
            return
        try:
            credentials = self._credentials(subscription)
        except HeadlessError:
            logger.warning(
                "Cannot stop remote jobs for subscription %s: credentials "
                "unavailable. Generation fencing still applies.",
                subscription.pk,
            )
            return

        client = DataLabHeadlessClient(
            credentials["datalab_username"],
            credentials["jupyter_token"],
            config=self._config(),
        )
        try:
            for job in active:
                from goats_tom.astro_data_lab.headless import JobHandle  # noqa: PLC0415

                try:
                    client.kill(
                        JobHandle(
                            username=job.datalab_username,
                            job_id=job.job_id,
                            session_id=job.session_id or "",
                            kernel_id=job.kernel_id or "",
                            pid=job.remote_pid,
                        )
                    )
                except Exception:
                    logger.warning(
                        "Could not kill remote job %s.", job.job_id, exc_info=True
                    )
            active.update(status=RemoteJob.Status.LOST, finished_at=timezone.now())
        finally:
            client.close()

    def status(self, subscription) -> dict[str, Any]:
        """Report the newest job's state for `subscription`."""
        job = RemoteJob.objects.filter(subscription=subscription).first()
        if job is None:
            return {"running": False}
        return {
            "running": job.is_active,
            "job_id": job.job_id,
            "state": job.status,
            "loci_seen": job.loci_seen,
            "loci_kept": job.loci_kept,
            "last_heartbeat": job.last_heartbeat,
            "error": job.error,
        }

    # -- collection --------------------------------------------------------

    def collect(self, subscription) -> list[dict[str, Any]]:
        """Rotate the PI's MyDB table aside and return its rows.

        Returns
        -------
        list of dict
            Rows written by this subscription's runners, oldest first.

        Warnings
        --------
        The caller must upsert these into `AntaresLocus` **before** calling
        `finish_collect`. The runner has already advanced its Kafka offsets
        past these alerts, so dropping the table before they are committed
        loses them permanently.

        Every field in the returned rows is a *claim*, not a fact. The runner
        and its spec are staged in a directory the PI can write to, so a PI
        could emit rows naming another subscription. The caller already knows
        which subscription it authenticated as and must use that, checking
        `generation` against the value it holds rather than adopting the
        row's.
        """
        credentials = self._credentials(subscription)
        db = MyDBClient(credentials["datalab_token"])
        drain = db.rotate_for_drain(loci_table_name())
        if drain is None:
            return []
        return db.drain(drain)

    def finish_collect(self, subscription) -> None:
        """Drop the drained table. Call only after rows are committed."""
        credentials = self._credentials(subscription)
        db = MyDBClient(credentials["datalab_token"])
        db.finish_drain(db.drain_table_name(loci_table_name()))
