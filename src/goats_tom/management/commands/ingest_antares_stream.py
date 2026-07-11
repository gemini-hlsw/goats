"""
Management command to start ANTARES Kafka stream ingestion.
"""

from django.core.management.base import BaseCommand

from goats_tom.tasks import ingest_antares_stream


class Command(BaseCommand):
    """
    Enqueues the `ingest_antares_stream` Dramatiq actor, which then blocks
    indefinitely consuming the ANTARES Kafka alert stream.

    This should be run once, in its own process, alongside `rundramatiq` and
    `run_scheduler` -- not from within `AppConfig.ready()`, since `ready()`
    runs in every process that imports `goats_tom` (the web server, every
    Dramatiq worker, and the scheduler), which would enqueue duplicate
    consumers.

    Example
    -------
    $ python manage.py ingest_antares_stream
    """

    help = "Starts the ANTARES Kafka alert stream consumer (runs indefinitely)."

    def handle(self, *args, **_opts):
        self.stdout.write("* Enqueuing ANTARES Kafka stream consumer...")
        ingest_antares_stream.send()
        self.stdout.write(
            "* Consumer enqueued. It will run on a Dramatiq worker process; "
            "check worker logs for stream activity."
        )
