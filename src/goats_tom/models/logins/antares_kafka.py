__all__ = ["AntaresKafkaLogin"]

from django.db import models
from goats_tom.encryption import EncryptedField

from .base import BaseLogin


class AntaresKafkaLogin(BaseLogin):
    """A login model for ANTARES Kafka streaming credentials.

    These are separate from any ANTARES Portal/REST API credentials --
    request them from the ANTARES team specifically for Kafka stream
    access. Any user may store their own: each ANTARES stream
    subscription runs its own Kafka consumer authenticating as the
    subscription's owner (see
    `goats_tom.models.AntaresStreamSubscription.owner`), because one Kafka
    connection authenticates as exactly one credential.

    Attributes
    ----------
    api_key : str
        The ANTARES Kafka streaming API key.
    api_secret : str
        The ANTARES Kafka streaming API secret.

    Notes
    -----
    The Kafka consumer group name is derived per subscription and
    optionally suffixed on the ingestion page (see
    `goats_tom.models.AntaresStreamSubscription.resolved_consumer_group`),
    not here -- it's changed far more often than the credentials
    themselves (e.g. to force a full replay from a fresh group with no
    committed offset), so keeping it separate means switching groups
    doesn't require re-entering API credentials each time.
    """

    api_key = EncryptedField(blank=False, null=True)
    api_secret = EncryptedField(blank=False, null=True)
