"""
Run APScheduler to enqueue Dramatiq jobs.
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand

from goats_tom.tasks.check_latest_version import check_version_info

JOBS = [
    {
        "id": "check_latest_version",
        "name": "check_latest_version",
        "func": check_version_info.send,
        "trigger": CronTrigger(hour="*"),
        "coalesce": True,
        "max_instances": 1,
        "replace_existing": True,
    },
]


class Command(BaseCommand):
    """
    Django management command that runs a quiet APScheduler.

    The command boots a `BlockingScheduler`, registers jobs defined in
    :data:`JOBS`, installs signal handlers for graceful shutdown, and starts
    the scheduler loop.
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

        for job in JOBS:
            scheduler.add_job(**job)

        def _stop(_sig, _frame):
            """
            Stop the scheduler and exit the process.

            Parameters
            ----------
            _sig : int
                Received POSIX signal number.
            _frame : types.FrameType | None
                Current stack frame (unused).
            """
            try:
                scheduler.shutdown(wait=False)
            finally:
                sys.exit(0)

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, _stop)

        self.stdout.write("Task scheduler running.")

        scheduler.start()
