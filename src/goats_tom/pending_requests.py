"""One place that answers "what is waiting on this user?".

GOATS has three approval flows and, before this module, three different ways
of surfacing them: account signups got a badged entry in the user menu,
ANTARES stream access got an unbadged line that appeared inside the
*Brokers* menu, and TNS group access got a second badged entry of its own.
Three conventions for one idea, and the ANTARES one gave a PI no indication
at all that somebody was waiting -- the line looked like ordinary navigation.

Collecting them here means the navbar renders whatever this returns rather
than knowing about any particular flow, and a fourth approval flow becomes
one entry in `_SOURCES` instead of another bespoke badge.

Nothing here is a permission check. A source only decides whether a user
*could* have anything pending; the pages behind the links do their own
authorisation.
"""

__all__ = ["PendingRequests", "pending_requests", "pending_request_total"]

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class PendingRequests:
    """One flow's pending items, ready to render.

    Attributes
    ----------
    key : str
        Short identifier, for tests and for templates that need to single
        one out.
    count : int
        How many are waiting. May be zero: an entry is returned whenever the
        flow *applies* to the user, not only when something is pending, so
        the queue stays reachable when it is empty. Removing the link at
        zero would leave an administrator with no way to open the
        registration queue except by typing the URL.
    label : str
        Fixed name of the queue. Deliberately short, and without the word
        "requests": these render beneath a "Manage Requests" heading that
        already supplies it, so repeating it in every child both read
        clumsily and was what pushed the menu wide enough for the badges to
        overflow it.
    url : str
        Where to go to deal with them.

    """

    key: str
    count: int
    label: str
    url: str


def _account_requests(user):
    """Account signups awaiting an administrator.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    `PendingRequests` or None
        `None` for non-administrators. Administrators always get an entry,
        with a count of zero when the queue is empty -- this is the only
        route to the registration queue, so it has to survive being empty.
    """
    if not user.is_superuser:
        return None

    from goats_tom.models import RegistrationRequest  # noqa: PLC0415

    return PendingRequests(
        key="account",
        count=RegistrationRequest.objects.filter(
            status=RegistrationRequest.STATUS_PENDING
        ).count(),
        label="Accounts",
        url=reverse("registration-requests"),
    )


def _antares_requests(user):
    """ANTARES stream access requests awaiting this PI.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    `PendingRequests` or None
        `None` unless the user is a PI; a PI with an empty queue still gets
        an entry, since this replaced the Brokers-menu link and is now the
        only way to reach the page.

    Notes
    -----
    Called "ANTARES stream access" rather than plain "ANTARES access",
    matching the "Live ANTARES Stream" entry these requests are actually
    about. A user with several kinds of ANTARES involvement should not have
    to guess which one is being asked for.
    """
    from goats_tom.models import AntaresGroupJoinRequest  # noqa: PLC0415

    if not hasattr(user, "antares_pi_group"):
        return None
    return PendingRequests(
        key="antares",
        count=AntaresGroupJoinRequest.objects.filter(
            pi_group__pi=user,
            status=AntaresGroupJoinRequest.STATUS_PENDING,
        ).count(),
        label="ANTARES Stream Access",
        url=reverse("antares-manage-access"),
    )


def _tns_requests(user):
    """TNS group access requests awaiting this bot owner.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    `PendingRequests` or None
        `None` unless the user owns at least one TNS group.
    """
    from goats_tom.models import TNSGroup, TNSGroupJoinRequest  # noqa: PLC0415

    if not TNSGroup.objects.filter(owner=user).exists():
        return None
    return PendingRequests(
        key="tns",
        count=TNSGroupJoinRequest.objects.filter(
            tns_group__owner=user,
            status=TNSGroupJoinRequest.STATUS_PENDING,
        ).count(),
        label="TNS Groups",
        url=reverse("user-tns-login", kwargs={"pk": user.pk}),
    )


_SOURCES = (_account_requests, _antares_requests, _tns_requests)
"""Every approval flow, in the order they appear in the menu.

Add a new flow by writing a function returning `PendingRequests` or `None`
and listing it here. The navbar needs no change.
"""


def pending_requests(user) -> list[PendingRequests]:
    """Everything waiting on `user`, across all approval flows.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    list of `PendingRequests`
        One entry per flow the user takes part in, whether or not anything
        is pending. Empty for anonymous users, and for users who administer
        nothing and own no groups.

    Notes
    -----
    Each source returns early for users the flow cannot apply to -- a
    non-administrator never queries account requests -- so an ordinary user
    with no groups triggers two cheap indexed counts and nothing more. Both
    filter on an indexed `status` column joined to an owner, which is the
    same shape of query the navbar already ran for account requests alone.
    """
    if user is None or not user.is_authenticated:
        return []
    return [
        result
        for result in (source(user) for source in _SOURCES)
        if result is not None
    ]


def pending_request_total(user) -> int:
    """Total number of items waiting on `user`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The viewer.

    Returns
    -------
    int
        Sum across all flows; zero when nothing is pending.

    Notes
    -----
    Backs the single badge on the username. One number covering everything
    is the point: a user should not have to open a menu, or know which
    flows exist, to find out that somebody is waiting on them.
    """
    return sum(entry.count for entry in pending_requests(user))
