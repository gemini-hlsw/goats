"""Email for the things that need a decision from someone who is not looking.

`goats_tom.realtime` covers transient status about work you started while
watching a page. This module covers the approval queues, where the table is
the source of truth and a real-time notification reaches only connected
sessions -- so nothing tells a decider a request is waiting unless they
happen to be signed in.

Every function here swallows its exceptions: the request is already recorded
and its queue page already shows it, so an unreachable SMTP server must not
cost somebody their access. `PasswordResetView` is deliberately **not**
routed through here -- it has no queue behind it, so a swallowed failure
would lock somebody out while telling them everything is fine.
"""

__all__ = [
    "notify_owner_of_tns_join_request",
    "notify_user_of_tns_join_decision",
]

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def _admin_addresses() -> list[str]:
    """Return the addresses administrator mail goes to.

    Returns
    -------
    list of str
        The configured addresses, falling back to the GOATS group address.

    Notes
    -----
    A configured address rather than every superuser, since a group address
    survives people leaving and the flag changing hands.
    """
    configured = getattr(settings, "GOATS_ADMIN_EMAILS", None)
    if isinstance(configured, str):
        return [configured]
    return list(configured or ["goats@noirlab.edu"])


def _site_url(path: str = "") -> str:
    """Return an absolute URL for `path`.

    Notes
    -----
    From `GOATS_SITE_URL`, since a background task has no request to derive a
    host from. Falls back to a relative path rather than guessing: a link to
    the wrong host may point at somebody else's instance.
    """
    base = getattr(settings, "GOATS_SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


def _subject_prefix() -> str:
    """The prefix every GOATS notification subject carries."""
    return getattr(settings, "GOATS_EMAIL_SUBJECT_PREFIX", "[GOATS] ")


def _send(subject: str, body: str, recipients: list[str], context: str) -> None:
    """Send one message, logging and swallowing any failure.

    Parameters
    ----------
    subject, body : str
        The message.
    recipients : list of str
        Where it goes. Empty is a no-op.
    context : str
        What this was about, for the log line when it fails.

    Notes
    -----
    Swallows deliberately; see the module docstring.
    """
    recipients = [address for address in recipients if address]
    if not recipients:
        logger.info("No recipient for %s; skipping email.", context)
        return

    try:
        send_mail(
            subject=f"{_subject_prefix()}{subject}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send email about %s.", context)


def notify_owner_of_tns_join_request(join_request) -> None:
    """Tell a credential owner that somebody wants to post through their group.

    Parameters
    ----------
    join_request : `goats_tom.models.TNSGroupJoinRequest`
        The pending request.

    Notes
    -----
    Goes to the owner and to the administrators, since a superuser may also
    decide these and an owner on an observing run should not hold up a
    collaboration.
    """
    requester = join_request.requester
    group = join_request.tns_group
    owner = group.owner

    body = (
        f"{requester.get_full_name() or requester.username} has asked to "
        f"post to the TNS through your group '{group.name}'.\n\n"
        f"Username: {requester.username}\n"
        f"Email:    {requester.email}\n\n"
        "If you approve, reports and classifications they submit for this "
        "group will be sent to the TNS using your bot credentials, and the "
        "TNS will attribute them to your bot.\n"
    )
    if join_request.message:
        body += f"\nMessage:\n{join_request.message}\n"
    body += (
        f"\nApprove or decline it here:\n"
        f"{_site_url(reverse('user-tns-login', kwargs={'pk': owner.pk}))}\n"
    )

    recipients = _admin_addresses()
    if owner is not None and owner.email:
        recipients = [owner.email, *recipients]

    _send(
        subject=f"{requester.username} asked to post via your TNS group",
        body=body,
        recipients=recipients,
        context=f"TNS join request from {requester.username}",
    )


def notify_user_of_tns_join_decision(join_request) -> None:
    """Tell a requester whether they may post through a group.

    Parameters
    ----------
    join_request : `goats_tom.models.TNSGroupJoinRequest`
        The decided request.

    Notes
    -----
    An approval spells out that posts go out under the owner's bot, which
    somebody used to posting as themselves has no reason to expect.
    """
    requester = join_request.requester
    group = join_request.tns_group

    if join_request.status == join_request.STATUS_APPROVED:
        subject = f"You can now post to the TNS via {group.name}"
        body = (
            f"Your request to post to the TNS through the group "
            f"'{group.name}' was approved.\n\n"
            f"Submissions you make for this group use "
            f"{group.owner.username}'s bot credentials and are attributed "
            "to that bot by the TNS. Check the author list on the form "
            "before submitting.\n\n"
            f"Open your targets here:\n{_site_url(reverse('targets:list'))}\n"
        )
    else:
        subject = f"Your TNS request for {group.name}"
        body = (
            f"Your request to post to the TNS through the group "
            f"'{group.name}' was not approved.\n\n"
            "Contact the group's owner if you think this is a mistake.\n"
        )

    _send(
        subject=subject,
        body=body,
        recipients=[requester.email],
        context=f"TNS join decision for {requester.username}",
    )
