__all__ = ["AntaresKafkaLogin"]

from django.db import models

from .base import BaseLogin


class AntaresKafkaLogin(BaseLogin):
    """A login model for ANTARES Kafka streaming credentials.

    These are separate from any ANTARES Portal/REST API credentials --
    request them from the ANTARES team specifically for Kafka stream
    access. Only superusers are permitted to store these (enforced by
    `goats_tom.views.logins.antares_kafka.AntaresKafkaLoginView`, not at
    the model level); the Kafka consumer uses the first superuser's stored
    credentials, since it runs as a single shared background process, not
    tied to any particular request/user.

    Attributes
    ----------
    api_key : str
        The ANTARES Kafka streaming API key.
    api_secret : str
        The ANTARES Kafka streaming API secret.
    group : str
        Optional Kafka consumer group name. If blank, a built-in default
        is used (see `goats_tom.tasks.ingest_antares_stream.DEFAULT_GROUP`).
    """

    api_key = models.CharField(max_length=128, blank=False, null=False)
    api_secret = models.CharField(max_length=128, blank=False, null=False)
    group = models.CharField(max_length=128, blank=True, null=False, default="")
