"""Password reset, with a readable failure when the mail server is down.

Everything about the flow is Django's: token generation, expiry, one-time
use, and the constant-time lookup that stops the form being used to
enumerate registered addresses. Those are subtly easy to get wrong and
Django's implementation is audited. Two things here are ours -- the
templates, and what a user sees when the send itself fails.

The bug this was written for
----------------------------
As of Django 5.2, `PasswordResetForm.send_mail` swallows every exception::

    try:
        email_message.send()
    except Exception:
        logger.exception("Failed to send password reset email to %s", ...)

Reasonable for Django's purposes -- it stops the response revealing whether
an address is registered, since a send only happens for a matching user. The
consequence is that **a completely unreachable mail server still produces the
"check your email" page**. The user waits for a link that was never sent, and
the only sign of trouble is a traceback in a log nobody is reading.

That was observed on a real deployment: the relay refused every message with
a 550 and the interface said the mail was on its way. An earlier version of
this module guarded `form_valid` and did nothing at all, because nothing ever
reached it.

`RecordingPasswordResetForm` notices the failure without changing what the
page reveals, and `GOATSPasswordResetView` turns it into an error on the
form. Both halves are needed.

What is deliberately preserved
------------------------------
The page still cannot say whether an account exists. A send is attempted only
for a matching user, so an unknown address takes the ordinary success path --
the same one it takes when the mail server is healthy. Only a real, attempted,
failed send produces the error.
"""

__all__ = ["GOATSPasswordResetView", "RecordingPasswordResetForm"]

import logging

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView

logger = logging.getLogger(__name__)


class RecordingPasswordResetForm(PasswordResetForm):
    """`PasswordResetForm` that remembers whether a send failed.

    Notes
    -----
    Django's `send_mail` catches everything and logs, so a failure is
    invisible to the caller. This records it on the form rather than
    re-raising: re-raising would change *when* the page differs. An unknown
    address never reaches `send_mail` at all, so an exception escaping only
    for known addresses would tell an attacker which is which.

    Recording keeps the two indistinguishable except in the one case that
    matters -- a message that was genuinely attempted and genuinely failed.

    The wrapping happens at `send_messages` on the connection, because that
    is precisely what Django's `try` block guards. Wrapping `send_mail`
    itself would sit *inside* the swallow and see nothing.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Set when a send was attempted and did not succeed.
        self.send_failed = False

    def save(self, *args, **kwargs):
        """Run the normal save, detecting a swallowed send failure."""
        from django.core import mail  # noqa: PLC0415

        original_get_connection = mail.get_connection
        form = self

        def recording_get_connection(*conn_args, **conn_kwargs):
            connection = original_get_connection(*conn_args, **conn_kwargs)
            original_send = connection.send_messages

            def send_messages(messages):
                try:
                    sent = original_send(messages)
                except Exception:
                    form.send_failed = True
                    raise
                if messages and not sent:
                    # Some backends report zero sent instead of raising.
                    form.send_failed = True
                return sent

            connection.send_messages = send_messages
            return connection

        mail.get_connection = recording_get_connection
        try:
            return super().save(*args, **kwargs)
        finally:
            # Restored even on failure: leaving this patched would affect
            # every other send in the process.
            mail.get_connection = original_get_connection


class GOATSPasswordResetView(PasswordResetView):
    """`PasswordResetView` that reports a send failure on the form itself.

    Notes
    -----
    Depends on `RecordingPasswordResetForm`; without it this class does
    nothing, because Django swallows the exception before `form_valid` could
    see it. That was the original bug.

    Only the send is treated this way. Anything else that raises is a real
    bug and is left to reach the 500 handler, where it belongs -- catching
    more widely would turn genuine faults into a friendly message about
    email.
    """

    form_class = RecordingPasswordResetForm

    def form_valid(self, form):
        """Send the reset link, reporting failure on the form.

        Parameters
        ----------
        form : `RecordingPasswordResetForm`
            The validated form.

        Returns
        -------
        `django.http.HttpResponse`
            The redirect to the done page, or the form re-rendered with an
            error.

        Notes
        -----
        The message names an address to contact. A user who cannot sign in
        and cannot reset has no other route back into the instance, so
        telling them only that it failed would leave them stuck.
        """
        try:
            response = super().form_valid(form)
        except Exception:
            self._log_failure()
            return self._report_failure(form)

        if getattr(form, "send_failed", False):
            self._log_failure()
            return self._report_failure(form)

        return response

    def _log_failure(self) -> None:
        """Record the failure for whoever runs this instance."""
        logger.exception(
            "Could not send a password reset email. Check EMAIL_BACKEND, the "
            "SMTP settings, and GOATS_EMAIL_HELO_DOMAIN if the relay requires "
            "one."
        )

    def _report_failure(self, form):
        """Re-render the form explaining that the send failed."""
        from django.conf import settings  # noqa: PLC0415

        contacts = getattr(settings, "GOATS_ADMIN_EMAILS", None) or [
            "goats@noirlab.edu"
        ]
        contact = contacts[0] if isinstance(contacts, (list, tuple)) else contacts

        form.add_error(
            None,
            "We could not send the reset email just now. This is a problem on "
            "our side, not with your address. Please try again shortly, or "
            f"contact {contact} if it keeps happening.",
        )
        return self.form_invalid(form)
