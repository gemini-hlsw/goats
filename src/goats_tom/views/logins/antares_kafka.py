__all__ = ["AntaresKafkaLoginView"]

from goats_tom.forms import AntaresKafkaLoginForm
from goats_tom.models import AntaresKafkaLogin

from .base import BaseLoginView


class AntaresKafkaLoginView(BaseLoginView):
    """View for storing a user's own ANTARES Kafka streaming credentials.

    Open to any user, not just superusers. Each ANTARES stream
    subscription authenticates as its owner using that owner's stored
    credentials (see
    `goats_tom.tasks.ingest_antares_stream._get_streaming_config`), since
    one Kafka connection authenticates as exactly one credential -- so a
    researcher who has been issued their own ANTARES Kafka credentials
    needs to be able to store them here and run their own dashboard.

    This was previously restricted with `SuperuserRequiredMixin`, on the
    reasoning that the consumer was a single shared process using the
    first superuser's credentials, making anyone else's entry silently
    unused. That no longer holds, and the restriction would now prevent
    exactly the intended use.

    Non-superusers remain unable to store credentials against *another*
    user's account: `BaseLoginView.dispatch` already rejects any request
    whose URL `pk` isn't the requesting user's own (superusers excepted,
    since the Credential Manager is also an admin tool). That guard, not
    this mixin, is what protects other users' secrets.
    """

    service_name = "ANTARES Kafka"
    service_description = (
        "Provide ANTARES Kafka streaming credentials to enable live alert "
        "stream ingestion. These are separate from any ANTARES Portal/REST "
        "API credentials -- request them from the ANTARES team "
        "specifically for Kafka stream access. Your own stream "
        "subscription connects using these credentials."
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
