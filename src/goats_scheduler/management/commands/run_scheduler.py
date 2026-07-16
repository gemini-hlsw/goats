"""
Run APScheduler to enqueue Dramatiq jobs.
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management.base import BaseCommand

# Ensure tasks are imported so that scheduled jobs are registered.
import goats_tom.tasks  # noqa: F401

from ...scheduling import SCHEDULED_JOBS


class Command(BaseCommand):
    """
    Django management command that runs a quiet APScheduler.

    This command:
      - Boots a BlockingScheduler
      - Registers all cron-decorated jobs from the registry
      - Resumes the ANTARES Kafka stream consumer exactly once, if a
        subscription was previously configured and left running (see
        `goats_tom.tasks.ingest_antares_stream` and
        `goats_tom.models.AntaresStreamSubscription`). Topics and
        credentials both come from stored configuration (the subscription
        row and a superuser's Credential Manager entry, respectively) --
        there is no settings-based fallback for either. This runs here,
        in the single scheduler process, rather than from
        `AppConfig.ready()`, which would fire in every process (web
        server, every Dramatiq worker) and enqueue duplicate consumers.
      - Installs signal handlers for graceful shutdown
      - Starts the scheduler loop
    """

    help = "Quiet APScheduler that enqueues Dramatiq jobs (no CLI args)."

    def handle(self, *args, **_opts):
        for name in (
            "apscheduler",
            "apscheduler.scheduler",
            "apscheduler.executors.default",
            "apscheduler.jobstores.default",
            "apscheduler.triggers",
        ):
            logger = logging.getLogger(name)
            logger.propagate = False

        scheduler = BlockingScheduler()

        if not SCHEDULED_JOBS:
            self.stdout.write("* No scheduled jobs found.")

        # Register all scheduled jobs.
        for job in SCHEDULED_JOBS:
            self.stdout.write(f"* Discovered tasks module: '{job['module_func']}'")
            scheduler.add_job(
                job["job_path"],
                trigger=job["trigger"],
                name=job["name"],
                coalesce=job["coalesce"],
                max_instances=job["max_instances"],
                replace_existing=job["replace_existing"],
            )

        self._resume_antares_stream_if_previously_running()

        def _stop(_sig, _frame):
            try:
                scheduler.shutdown(wait=False)
            finally:
                sys.exit(0)

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, _stop)

        self.stdout.write("* Running Task Scheduler")
        scheduler.start()

    def _resume_antares_stream_if_previously_running(self) -> None:
        """Re-enqueue the ANTARES Kafka stream consumer on startup, if a
        subscription exists and was left in a running state.

        Skips quietly if no subscription has ever been configured (most
        GOATS installs won't use ANTARES streaming), or if the last
        subscription was explicitly stopped. Does not validate that
        credentials are actually present -- if they're missing, the actor
        itself raises and logs a clear error (see
        `goats_tom.tasks.ingest_antares_stream._get_streaming_config`)
        rather than this command silently failing to start it.
        """
        from goats_tom.models import AntaresStreamSubscription
        from goats_tom.tasks import ingest_antares_stream

        subscription = (
            AntaresStreamSubscription.objects.order_by("-updated_at").first()
        )
        if subscription is None or not subscription.is_running:
            self.stdout.write(
                "* No active ANTARES Kafka stream subscription to resume."
            )
            return

        self.stdout.write(
            f"* Resuming ANTARES Kafka stream consumer for topics: "
            f"{subscription.topics}"
        )
        message = ingest_antares_stream.send(
            topics=subscription.topics,
            handler_code=subscription.handler_code,
            save_all_targets=subscription.save_all_targets,
        )
        subscription.dramatiq_message_id = message.message_id
        subscription.save(update_fields=["dramatiq_message_id"])
