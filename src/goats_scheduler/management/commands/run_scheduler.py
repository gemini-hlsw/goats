"""
Run APScheduler to enqueue Dramatiq jobs.
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
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
      - Enqueues the long-running ANTARES Kafka stream consumer exactly
        once, if ANTARES_KAFKA_* settings are configured (see
        `goats_tom.tasks.ingest_antares_stream`). This runs here, in the
        single scheduler process, rather than from `AppConfig.ready()`,
        which would fire in every process (web server, every Dramatiq
        worker) and enqueue duplicate consumers.
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

        self._start_antares_stream_if_configured()

        def _stop(_sig, _frame):
            try:
                scheduler.shutdown(wait=False)
            finally:
                sys.exit(0)

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, _stop)

        self.stdout.write("* Running Task Scheduler")
        scheduler.start()

    def _start_antares_stream_if_configured(self) -> None:
        """Enqueue the ANTARES Kafka stream consumer, once, if configured.

        Skips quietly (with a message) if `ANTARES_KAFKA_TOPICS` isn't set,
        rather than raising -- most GOATS installs won't have ANTARES
        streaming credentials, and that should not prevent `goats run` from
        starting everything else.
        """
        from goats_tom.tasks import ingest_antares_stream

        if not getattr(settings, "ANTARES_KAFKA_TOPICS", None):
            self.stdout.write(
                "* ANTARES_KAFKA_TOPICS not set; skipping ANTARES stream consumer."
            )
            return

        self.stdout.write("* Enqueuing ANTARES Kafka stream consumer...")
        ingest_antares_stream.send()
