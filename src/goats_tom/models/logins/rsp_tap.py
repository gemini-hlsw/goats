__all__ = ["RSPTapLogin"]

from django.db import models

from .base import BaseLogin


class RSPTapLogin(BaseLogin):
    """A login model for Rubin Science Platform (RSP) TAP service access.

    Unlike ANTARES Kafka credentials (deliberately shared/superuser-scoped,
    since ANTARES issues a small number of credentials per team/institution,
    not per individual), an RSP access token is a personal, per-researcher
    credential -- any logged-in user may store their own (no superuser
    restriction, matching how GPP credentials are handled). See
    https://rsp.lsst.io/guides/auth/creating-user-tokens.html for how to
    create one.

    Used by ANTARES custom locus handler code (see
    `goats_tom.antares_locus_handler`) to query Rubin catalog data via the
    TAP service's ADQL interface, through the pre-bound `RSP_tap_service`
    name -- e.g. ``RSP_tap_service.run_async("SELECT ...").to_table()``.
    Handler code runs under `AntaresStreamSubscription.owner`'s
    own stored token, not a superuser's, for the same reason GPP
    triggering does: this is personal access, not shared infrastructure.

    Attributes
    ----------
    access_token : str
        The user's RSP access token (see "Creating user tokens" above).
        Used as the password half of HTTP Basic Auth, with username
        ``x-oauth-basic``, per RSP's documented "External access" pattern
        for TAP clients outside the RSP Notebook environment (where an
        auth session would otherwise be provisioned automatically).
    """

    access_token = models.CharField(max_length=256, blank=False, null=False)
