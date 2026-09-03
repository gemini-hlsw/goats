"""An SMTP backend that introduces itself with a domain you choose.

Why this exists
---------------
Google Workspace's SMTP relay will not accept mail from a host it cannot
attribute to your domain. It checks two things: that the connecting address
is on the allowlist, and that the ``EHLO`` greeting names a domain it
recognises. Django sends the machine's own fully-qualified name in that
greeting, which for a laptop or a cloud VM is something like
``goats-server.local`` -- on the allowlist, but meaningless to Google.

The refusal says so directly::

    550 5.7.1 The IP address you've registered in your Workspace SMTP Relay
    service doesn't match the domain of the account this email is being sent
    from. ... you must configure your mail server either to use SMTP AUTH to
    identify the sending domain or to present one of your domain names in the
    HELO or EHLO command.

This takes the second option. Nothing about the network changes and no
credentials are involved -- only the name announced at the start of the
conversation.

Why a subclass
--------------
`django.core.mail.backends.smtp.EmailBackend` builds its connection with
``local_hostname=DNS_NAME.get_fqdn()`` and exposes no way to override it. The
alternative would be reassigning Django's module-level `DNS_NAME`, which
changes the greeting for every SMTP connection in the process and is the kind
of action-at-a-distance that is impossible to find later. Overriding
`open` keeps it to the one backend that was configured to do it.

Not required for every relay. `GOATS_EMAIL_HELO_DOMAIN` is empty by default,
in which case this behaves exactly as Django's backend and sends the
machine's own name.
"""

__all__ = ["HeloEmailBackend"]

import logging

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)


class HeloEmailBackend(EmailBackend):
    """SMTP backend that announces `GOATS_EMAIL_HELO_DOMAIN` in ``EHLO``.

    Notes
    -----
    Set `GOATS_EMAIL_HELO_DOMAIN` to a domain the relay recognises -- for
    NOIRLab, ``noirlab.edu``. Leave it unset for any relay that does not care,
    and this is Django's backend unchanged.

    The override is applied by temporarily replacing the cached FQDN Django
    reads, rather than by reimplementing `open`. That method handles TLS
    setup, partial-connection cleanup and `fail_silently`, none of which is
    worth copying to change one string -- a copy would also silently fall
    behind whatever Django changes there next.
    """

    def open(self):
        """Open a connection, announcing the configured domain.

        Returns
        -------
        bool or None
            As `EmailBackend.open`.
        """
        helo_domain = getattr(settings, "GOATS_EMAIL_HELO_DOMAIN", "") or ""
        if not helo_domain:
            return super().open()

        from django.core.mail.utils import DNS_NAME  # noqa: PLC0415

        original = DNS_NAME._fqdn if hasattr(DNS_NAME, "_fqdn") else None
        DNS_NAME._fqdn = helo_domain
        try:
            logger.debug("Opening SMTP connection announcing %s.", helo_domain)
            return super().open()
        finally:
            # Restored even if the connection failed. Leaving it set would
            # change the greeting for every other SMTP user in this process,
            # which is exactly the action-at-a-distance this class avoids.
            if original is None:
                DNS_NAME.__dict__.pop("_fqdn", None)
            else:
                DNS_NAME._fqdn = original
