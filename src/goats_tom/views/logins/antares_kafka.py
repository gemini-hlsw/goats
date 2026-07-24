__all__ = ["AntaresKafkaLoginView"]

from tom_common.mixins import SuperuserRequiredMixin

from goats_tom.forms import AntaresKafkaLoginForm
from goats_tom.models import AntaresKafkaLogin

from .base import BaseLoginView


class AntaresKafkaLoginView(SuperuserRequiredMixin, BaseLoginView):
    """View for storing ANTARES Kafka streaming credentials.

    Restricted to superusers: the Kafka consumer runs as a single shared
    background process (not tied to any particular request/user), and
    uses the first superuser's stored credentials (see
    `goats_tom.tasks.ingest_antares_stream._get_streaming_config`) -- so
    only superusers are allowed to store them here, to avoid the
    confusing situation of a non-superuser saving credentials that are
    silently never used.
    """

    service_name = "ANTARES Kafka"
    service_description = (
        "Provide ANTARES Kafka streaming credentials to enable live alert "
        "stream ingestion. These are separate from any ANTARES Portal/REST "
        "API credentials -- request them from the ANTARES team "
        "specifically for Kafka stream access. Only superusers can store "
        "these, since the stream consumer uses the first superuser's "
        "credentials."
    )
    model_class = AntaresKafkaLogin
    form_class = AntaresKafkaLoginForm
    credentials_are_verifiable = False

    def perform_login_and_logout(self, **kwargs) -> bool:
        # No live verification available for Kafka streaming credentials
        # without actually opening a stream connection, which isn't worth
        # doing synchronously in a form submission -- same approach TNS
        # takes for its own unverifiable credentials. See
        # `credentials_are_verifiable = False` above: this is what makes
        # the post-save message honestly say "saved" rather than falsely
        # claim "verified" (the base view's default assumption for
        # anything reaching this success path).
        return True
