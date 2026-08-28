__all__ = ["RSPTapLoginView"]

from django.utils.safestring import mark_safe

from goats_tom.forms import RSPTapLoginForm
from goats_tom.models import RSPTapLogin

from .base import BaseLoginView


class RSPTapLoginView(BaseLoginView):
    """View for storing Rubin Science Platform (RSP) TAP access tokens.

    Not restricted to superusers: unlike ANTARES Kafka credentials
    (shared/superuser-scoped, since ANTARES issues a small number of
    credentials per team/institution), an RSP access token is a personal,
    per-researcher credential -- any logged-in user may store their own,
    same as GPP.
    """

    service_name = "RSP TAP"
    service_description = mark_safe(
        "Provide your Rubin Science Platform (RSP) access token to query "
        "Rubin catalog data from custom ANTARES locus handler code via "
        "the TAP service. See "
        '<a href="https://rsp.lsst.io/guides/auth/creating-user-tokens.html" '
        'target="_blank" rel="noopener noreferrer">Creating user tokens</a> '
        "for how to create one."
    )
    model_class = RSPTapLogin
    form_class = RSPTapLoginForm
    credentials_are_verifiable = False

    def perform_login_and_logout(self, **kwargs) -> bool:
        # No live verification available without actually issuing a real
        # TAP query, which isn't worth doing synchronously in a form
        # submission -- same approach TNS/ANTARES Kafka take for their
        # own unverifiable credentials. See `credentials_are_verifiable
        # = False` above: this is what makes the post-save message
        # honestly say "saved" rather than falsely claim "verified".
        return True
