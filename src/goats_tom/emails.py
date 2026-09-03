"""Email for the things that need a decision from someone who is not looking.

GOATS already notifies in real time through `goats_tom.realtime`, and those
notifications are right for what they do: transient status about work you
started while watching a page. Download progress and reduction status belong
there and nowhere else.

This module covers a different set. Both `RegistrationRequest` and
`AntaresGroupJoinRequest` say the same thing in their docstrings -- the table
is the source of truth, and the real-time notification "is delivered only to
connected sessions, so anything that depended on it would silently lose
requests made while the PI was offline". Email is the durable channel onto
those tables: a request sits in a queue until somebody decides it, and
nothing tells them it is there unless they happen to be signed in.

Failures never block
--------------------
Every function here swallows its exceptions. A registration is recorded, its
toast fires and the queue page shows it whether or not mail sends. An
unreachable SMTP server must not cost somebody their account request.

`django.contrib.auth.views.PasswordResetView` is the exception and is
deliberately **not** routed through here. It sends synchronously, while the
user waits on the page, because there is no queue behind it -- a swallowed
failure there means somebody is locked out and told everything is fine.
"""

__all__ = [
    "notify_admins_of_registration",
    "notify_pi_of_join_request",
    "notify_user_of_join_decision",
    "notify_user_of_registration_decision",
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

    Notes
    -----
    A configured address rather than every superuser. Superuser accounts
    change, a shared server should not mail whoever currently holds the flag,
    and a group address survives people leaving.
    """
    configured = getattr(settings, "GOATS_ADMIN_EMAILS", None)
    if isinstance(configured, str):
        return [configured]
    return list(configured or ["goats@noirlab.edu"])


def _site_url(path: str = "") -> str:
    """Return an absolute URL for `path`.

    Notes
    -----
    Built from `GOATS_SITE_URL` because a background task has no request to
    derive a host from, and a relative link in an email is not clickable.
    Falls back to a relative path rather than guessing a hostname: a link to
    the wrong host is worse than no link, since it may point at somebody
    else's instance.
    """
    base = getattr(settings, "GOATS_SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


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
    Swallows deliberately. See the module docstring: the request is already
    recorded, and mail is the second channel onto it, not the first.
    """
    recipients = [address for address in recipients if address]
    if not recipients:
        logger.info("No recipient for %s; skipping email.", context)
        return

    try:
        send_mail(
            subject=f"{getattr(settings, 'GOATS_EMAIL_SUBJECT_PREFIX', '[GOATS] ')}{subject}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send email about %s.", context)


def notify_admins_of_registration(registration) -> None:
    """Tell administrators that somebody has asked for an account.

    Parameters
    ----------
    registration : `goats_tom.models.RegistrationRequest`
        The pending request.

    Notes
    -----
    Includes the applicant's stated reason, because an administrator
    approving an unfamiliar username otherwise has nothing to go on -- the
    same argument the model makes for storing it.

    Does **not** include the requested groups as though they were granted.
    The form is public, so what was asked for and what is granted are
    different things, and an email that read like an assignment would invite
    an administrator to approve without looking.
    """
    user = registration.user
    requested = ", ".join(
        group.name for group in registration.requested_groups.all()
    )

    body = (
        f"{user.get_full_name() or user.username} has requested a GOATS account.\n\n"
        f"Username: {user.username}\n"
        f"Email:    {user.email}\n"
    )
    if requested:
        body += f"Groups requested (not yet granted): {requested}\n"
    if registration.reason:
        body += f"\nReason given:\n{registration.reason}\n"
    body += (
        f"\nReview it here:\n{_site_url(reverse('registration-requests'))}\n"
    )

    _send(
        subject=f"Account request from {user.username}",
        body=body,
        recipients=_admin_addresses(),
        context=f"registration request from {user.username}",
    )


def notify_user_of_registration_decision(registration) -> None:
    """Tell an applicant whether their account was approved.

    Parameters
    ----------
    registration : `goats_tom.models.RegistrationRequest`
        The decided request.

    Notes
    -----
    A rejection says only that it was not approved, with an address to reply
    to. Recording a reason is not part of the model, and inventing wording
    that implies one would be worse than saying plainly that there is a human
    to ask.
    """
    user = registration.user

    if registration.status == registration.STATUS_APPROVED:
        subject = "Your GOATS account has been approved"
        body = (
            f"Your GOATS account ({user.username}) has been approved.\n\n"
            f"You can sign in here:\n{_site_url(reverse('login'))}\n"
        )
    else:
        subject = "Your GOATS account request"
        body = (
            f"Your request for a GOATS account ({user.username}) was not "
            "approved.\n\n"
            f"If you think this is a mistake, reply to "
            f"{_admin_addresses()[0]}.\n"
        )

    _send(
        subject=subject,
        body=body,
        recipients=[user.email],
        context=f"registration decision for {user.username}",
    )


def notify_pi_of_join_request(join_request) -> None:
    """Tell a PI that somebody has asked to join their group.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The pending request.

    Notes
    -----
    Goes to the PI and to the administrators, because a superuser may also
    decide these -- the model says so -- and a PI who has left or is on
    observing runs should not block everyone behind them.

    States what was *asked for*, not what will be granted. The PI decides the
    permissions separately, and the model keeps the two distinguishable
    precisely so a narrower grant is not mistaken for the request.
    """
    requester = join_request.requester
    group = join_request.pi_group
    # `pi`, not `owner`: `AntaresPIGroup` names the person who owns the
    # group `pi`, while the *subscription* uses `owner`. Reading the wrong
    # one returns None and the PI silently never hears about the request.
    pi = getattr(group, "pi", None)

    asked = ["view the dashboard"] if join_request.requested_view_dashboard else []
    if join_request.requested_save_targets:
        asked.append("save loci as targets")

    body = (
        f"{requester.get_full_name() or requester.username} has asked to join "
        f"your ANTARES group '{group}'.\n\n"
        f"Username: {requester.username}\n"
        f"Email:    {requester.email}\n"
        f"Asked to: {', '.join(asked) or 'join the group'}\n"
    )
    if join_request.message:
        body += f"\nMessage:\n{join_request.message}\n"
    body += (
        f"\nApprove or deny it here:\n"
        f"{_site_url(reverse('antares-manage-access'))}\n"
    )

    recipients = _admin_addresses()
    if pi is not None and pi.email:
        recipients = [pi.email, *recipients]

    _send(
        subject=f"{requester.username} asked to join your ANTARES group",
        body=body,
        recipients=recipients,
        context=f"join request from {requester.username}",
    )


def notify_user_of_join_decision(join_request) -> None:
    """Tell a requester whether they were let into a group.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The decided request.

    Notes
    -----
    An approval reports what was **granted**, read from the membership row,
    not what was requested. A PI may approve a narrower set of permissions,
    and telling somebody they can save targets when they cannot would send
    them to a button that refuses them.
    """
    requester = join_request.requester
    group = join_request.pi_group

    if join_request.status == join_request.STATUS_APPROVED:
        from goats_tom.models import AntaresDashboardMembership  # noqa: PLC0415

        membership = AntaresDashboardMembership.objects.filter(
            user=requester, pi_group=group
        ).first()

        granted = []
        if membership is not None:
            if getattr(membership, "can_view_dashboard", False):
                granted.append("view the dashboard")
            if getattr(membership, "can_save_targets", False):
                granted.append("save loci as targets")

        subject = f"You have been added to {group}"
        body = (
            f"You have been added to the ANTARES group '{group}'.\n\n"
            f"You can: {', '.join(granted) or 'view the group'}\n\n"
            f"Open the dashboard here:\n"
            f"{_site_url(reverse('antares-locus-dashboard'))}\n"
        )
    else:
        subject = f"Your request to join {group}"
        body = (
            f"Your request to join the ANTARES group '{group}' was not "
            "approved.\n\nContact the group's PI if you think this is a "
            "mistake.\n"
        )

    _send(
        subject=subject,
        body=body,
        recipients=[requester.email],
        context=f"join decision for {requester.username}",
    )
