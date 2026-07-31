"""Template tags for account registration."""

from django import template

from goats_tom.models import RegistrationRequest

register = template.Library()


@register.simple_tag
def pending_registration_count() -> int:
    """Number of account requests awaiting a decision.

    Returns
    -------
    int
        Count of `goats_tom.models.RegistrationRequest` rows still pending.

    Notes
    -----
    Used for the badge on the navbar's "Account Requests" entry. That badge is
    the only reliable way an administrator learns of a request: the real-time
    notification sent at registration reaches connected sessions only, so
    anyone who was signed out at the time -- the usual case, since people tend
    to register outside working hours -- would otherwise see nothing at all
    until they happened to open the queue.

    A template tag rather than a context processor, so the query runs only
    where it is rendered. The navbar guards the call with
    ``{% if user.is_superuser %}``, so ordinary users never pay for it.
    """
    return RegistrationRequest.objects.filter(
        status=RegistrationRequest.STATUS_PENDING
    ).count()
