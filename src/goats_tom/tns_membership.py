"""Join requests, memberships and posting options for shared TNS groups.

Kept out of the views for the same reasons as
`goats_tom.antares_membership`: the state changes are testable on their own,
and there is one place that knows how a request becomes a membership. Views
handle HTTP and permissions; this module handles what actually happens.

The one piece that has no ANTARES equivalent is `posting_options`. Every
other question here is about *permission*; that one is about which set of
credentials a given request should go out under, and it is the only thing
allowed to answer it. Both `goats_tom.middleware.tns` (which builds the
payload) and `goats_tom.views.tns_report` (which draws the picker) call it,
so the page can never offer a choice the middleware would then refuse.
"""

__all__ = [
    "TNSJoinRequestError",
    "PostingOption",
    "sync_groups_for_login",
    "shareable_groups",
    "requestable_groups",
    "posting_options",
    "resolve_posting_option",
    "create_join_request",
    "approve_join_request",
    "deny_join_request",
    "revoke_membership",
]

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from goats_tom.models import (
    TNSGroup,
    TNSGroupJoinRequest,
    TNSGroupMembership,
    TNSLogin,
)
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)


class TNSJoinRequestError(Exception):
    """Raised when a join request or decision cannot proceed."""


@dataclass(frozen=True)
class PostingOption:
    """One set of TNS credentials a user may submit with.

    An option is a **bot**, not a group. Those are two different choices and
    the form already makes the second one: `tom_tns`'s "Reporting group"
    field picks which TNS group a report is filed under, so a picker that
    also listed groups asked the same question twice and left the user with
    an entry reading "your own bot, no group", which describes an
    implementation detail rather than anything an astronomer would recognise.

    Choosing the bot decides whose credentials go out; the groups that bot
    may file under then populate Reporting group.

    Attributes
    ----------
    key : str
        Opaque identifier used in the picker and the session. ``"own"`` for
        the user's own credentials, or ``"owner:<pk>"`` for somebody else's.
    label : str
        What the picker shows -- the bot name, since that is what the TNS
        records the submission against.
    owner : `django.contrib.auth.models.User`
        Whose credentials the report goes out under.
    groups : tuple
        The `goats_tom.models.TNSGroup` rows this option may file under.
        Every live group for the user's own bot; only the granted ones for
        somebody else's, which is what stops a grant on one group widening
        to the owner's others.
    is_own : bool
        Whether these are the acting user's own credentials.

    """

    key: str
    label: str
    owner: object
    groups: tuple = ()
    is_own: bool = False

    @property
    def group_authors(self) -> dict:
        """Recommended co-authors per group name.

        Returns
        -------
        dict
            Group name to author list, skipping groups with none set.

        Notes
        -----
        Carried alongside the credentials so the report form can update its
        author field when Reporting group changes. The author list is a
        per-group setting but the group is chosen after the page has
        loaded, so a single pre-filled value would silently be the wrong
        one as soon as the user switched groups.
        """
        return {
            group.name: group.recommended_authors.strip()
            for group in self.groups
            if group.recommended_authors.strip()
        }


def _notify(
    user,
    label: str,
    message: str,
    color: str = "primary",
    autohide: bool = True,
) -> None:
    """Send one notification to one user, after the current transaction commits.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The recipient. Addressed privately -- these name other users and
        reveal who is posting through whose bot, so they must not be
        broadcast to every connected client.
    label : str
        Notification heading.
    message : str
        Notification body. Plain text, never HTML: it interpolates a
        username, and keeping it plain removes any question of escaping
        user-controlled content.
    color : str, optional
        Bootstrap colour scheme.
    autohide : bool, optional
        Whether the toast dismisses itself. Passed as `False` for anything
        that needs an action from the recipient, so it stays on screen until
        acknowledged rather than disappearing while they are looking
        elsewhere.

    Notes
    -----
    Deferred with `transaction.on_commit`, so nobody is told about a change
    that then rolls back. Outside an atomic block Django runs the callback
    immediately, which is correct for unwrapped callers too.

    Failures are logged and swallowed. The database is the source of truth
    for pending requests and memberships; an unreachable channel layer must
    not fail the operation that triggered it.
    """

    def _send() -> None:
        try:
            NotificationInstance.create_and_send(
                label=label,
                message=message,
                color=color,
                autohide=autohide,
                user=user,
            )
        except Exception:
            logger.exception(
                "Failed to notify user %s; the underlying change was still "
                "saved.",
                getattr(user, "username", None),
            )

    transaction.on_commit(_send)


def sync_groups_for_login(login: TNSLogin) -> None:
    """Bring `TNSGroup` rows into line with a login's `group_names`.

    Parameters
    ----------
    login : `goats_tom.models.TNSLogin`
        The credentials just saved.

    Notes
    -----
    Adds rows for names that are new and does **not** touch rows for names
    that are still present -- re-saving credentials must not silently reset
    somebody's sharing toggle or wipe an author list they curated.

    Rows for names no longer listed are kept, not deleted. Deleting would
    cascade away the memberships and the request history, so a typo in the
    group-names box, corrected a minute later, would quietly revoke access
    for everyone who had it. A stale row is invisible instead: anything
    that offers groups filters on the current name list (see
    `shareable_groups`), so an unlisted group is simply never shown while
    its settings wait to be picked up again if the name comes back.
    """
    names = [name.strip() for name in (login.group_names or []) if name.strip()]
    seen = set()
    for name in names:
        # Two entries that differ only by surrounding whitespace collapse to
        # the same group once stripped, and the unique constraint would
        # reject the second -- turning a stray space in the group-names box
        # into an IntegrityError on save. A duplicate means the user listed
        # one group twice, so collapsing them is what they meant.
        if name in seen:
            continue
        seen.add(name)
        # `get_or_create` rather than a pre-computed set of existing names:
        # it leaves a group that is already present untouched, so re-saving
        # credentials never resets a sharing toggle or author list, and it
        # closes the race between two concurrent saves that a read-then-write
        # would leave open.
        TNSGroup.objects.get_or_create(owner=login.user, name=name)


def _current_group_names(user) -> list[str]:
    """Return the group names currently listed on `user`'s credentials.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The credential owner.

    Returns
    -------
    list of str
        Empty if they have no credentials stored.
    """
    login = getattr(user, "tnslogin", None)
    if login is None:
        return []
    return [name.strip() for name in (login.group_names or []) if name.strip()]


def shareable_groups():
    """Every group that is opted in, and whose owner still has credentials.

    Returns
    -------
    `django.db.models.QuerySet`
        `TNSGroup` rows with `allow_join_requests` set, excluding any whose
        owner has since deleted their credentials or dropped the group from
        their list.

    Notes
    -----
    The `tnslogin__isnull` filter is what stops the page offering a group
    that cannot actually be posted through. A `TNSGroup` outlives the
    credentials it describes on purpose (see
    `goats_tom.models.TNSGroup.has_credentials`), so "opted in" and
    "usable" are genuinely different questions.

    Stale names are filtered in Python rather than SQL because the live
    list lives in a `JSONField` that cannot be joined against.
    """
    candidates = (
        TNSGroup.objects.filter(allow_join_requests=True)
        .exclude(owner__tnslogin__isnull=True)
        .select_related("owner", "owner__tnslogin")
        .order_by("name")
    )
    live = {
        group.pk
        for group in candidates
        if group.name in _current_group_names(group.owner)
    }
    return candidates.filter(pk__in=live)


def requestable_groups(user):
    """Groups `user` could ask to join.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The prospective member.

    Returns
    -------
    `django.db.models.QuerySet`
        Shareable groups excluding the user's own, any they already belong
        to, and any with a request already pending.

    Notes
    -----
    Filtering here rather than rejecting afterwards means a user is never
    offered a choice that cannot succeed.
    """
    if user is None or not user.is_authenticated:
        return TNSGroup.objects.none()

    return (
        shareable_groups()
        .exclude(owner=user)
        .exclude(memberships__user=user)
        .exclude(
            join_requests__requester=user,
            join_requests__status=TNSGroupJoinRequest.STATUS_PENDING,
        )
    )


def posting_options(user) -> list[PostingOption]:
    """Every set of credentials `user` may submit to the TNS with.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The acting user.

    Returns
    -------
    list of `PostingOption`
        The user's own bot first, if they have one, then one option per
        other owner whose group they have been granted.

    Notes
    -----
    One option per *bot*, not per group. A user granted three groups
    belonging to the same colleague gets one entry, with all three offered
    in Reporting group -- listing the bot three times would suggest three
    different sets of credentials.

    Own credentials come first so they are the default selection; someone
    with their own bot should not have to re-pick it each visit.

    A membership whose owner has since deleted their credentials, or who has
    dropped the group from their list, is skipped rather than offered and
    then failed.
    """
    if user is None or not user.is_authenticated:
        return []

    options: list[PostingOption] = []
    own_login = getattr(user, "tnslogin", None)

    if own_login is not None:
        own_names = _current_group_names(user)
        own_groups = tuple(
            TNSGroup.objects.filter(owner=user, name__in=own_names).order_by(
                "name"
            )
        )
        options.append(
            PostingOption(
                key="own",
                label=f"{own_login.bot_name} (yours)",
                owner=user,
                groups=own_groups,
                is_own=True,
            )
        )

    memberships = (
        TNSGroupMembership.objects.filter(user=user)
        .exclude(tns_group__owner=user)
        .select_related("tns_group", "tns_group__owner")
        .order_by("tns_group__owner__username", "tns_group__name")
    )
    by_owner: dict[int, list] = {}
    for membership in memberships:
        group = membership.tns_group
        if not group.has_credentials:
            continue
        if group.name not in _current_group_names(group.owner):
            continue
        by_owner.setdefault(group.owner_id, []).append(group)

    for groups in by_owner.values():
        owner = groups[0].owner
        login = owner.tnslogin
        # Full name only, never the username. A username is half of a login
        # credential and identifies nobody to a colleague; the bot name is
        # what the option is really about, so an owner with no full name set
        # simply shows as the bot alone.
        who = owner.get_full_name().strip()
        label = f"{login.bot_name} ({who})" if who else login.bot_name
        options.append(
            PostingOption(
                key=f"owner:{owner.pk}",
                label=label,
                owner=owner,
                groups=tuple(groups),
            )
        )

    return options


def resolve_posting_option(user, key: str | None) -> PostingOption | None:
    """Turn a picker `key` back into an option the user actually holds.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The acting user.
    key : str or None
        The key submitted or held in the session. `None` or unrecognised
        falls back to the first available option.

    Returns
    -------
    `PostingOption` or None
        `None` when the user has no way to post at all.

    Notes
    -----
    This is the authorisation check, not a convenience lookup. The key
    arrives from the session or a form field, both of which the user
    controls, so it is matched against the freshly-computed list of what
    they hold rather than trusted -- a hand-edited ``group:<pk>`` for
    somebody else's group finds no match and falls back.

    Falling back rather than raising is deliberate: access can be revoked
    between choosing an option and using it, and the right response to that
    is to quietly post as something the user does still hold, having shown
    them which, not to error out mid-submission.
    """
    options = posting_options(user)
    if not options:
        return None
    if key:
        for option in options:
            if option.key == key:
                return option
    return options[0]


def create_join_request(requester, tns_group, message: str = ""):
    """Create a pending request to post through a group.

    Parameters
    ----------
    requester : `django.contrib.auth.models.User`
        The user asking.
    tns_group : `goats_tom.models.TNSGroup`
        The group being asked for.
    message : str, optional
        Note to the owner.

    Returns
    -------
    `goats_tom.models.TNSGroupJoinRequest`
        The created request.

    Raises
    ------
    TNSJoinRequestError
        If the user owns the group, already belongs to it, the group is not
        accepting requests, or a request is already pending.

    Notes
    -----
    The checks are re-checked by the partial unique constraint on pending
    requests (see `TNSGroupJoinRequest.Meta`). Both exist on purpose: the
    checks give a readable error, the constraint closes the race between
    two rapid submissions that no amount of checking in Python can.
    """
    if requester is None or not requester.is_authenticated:
        raise TNSJoinRequestError("You must be signed in to request access.")

    if tns_group.owner_id == requester.pk:
        raise TNSJoinRequestError("You already own this group.")

    if not tns_group.allow_join_requests:
        raise TNSJoinRequestError(
            "That group is not accepting requests at the moment."
        )

    if TNSGroupMembership.objects.filter(
        tns_group=tns_group, user=requester
    ).exists():
        raise TNSJoinRequestError("You can already post through this group.")

    try:
        join_request = TNSGroupJoinRequest.objects.create(
            requester=requester,
            tns_group=tns_group,
            message=message,
        )
    except IntegrityError as exc:
        raise TNSJoinRequestError(
            "You already have a pending request for this group."
        ) from exc

    _notify(
        tns_group.owner,
        label="TNS group request",
        message=(
            f"{requester.username} has asked to report under your TNS group "
            f"'{tns_group.name}'."
        ),
        color="warning",
        # Needs a decision from the owner, so it stays until dismissed. An
        # auto-hiding toast is fine for "here is some news" and wrong for
        # "somebody is waiting on you".
        autohide=False,
    )
    return join_request


def approve_join_request(join_request, decided_by) -> TNSGroupMembership:
    """Approve a request and create the membership.

    Parameters
    ----------
    join_request : `goats_tom.models.TNSGroupJoinRequest`
        The pending request.
    decided_by : `django.contrib.auth.models.User`
        Who is approving -- normally the group's owner.

    Returns
    -------
    `goats_tom.models.TNSGroupMembership`
        The created or updated membership.

    Raises
    ------
    TNSJoinRequestError
        If the request is not pending.

    Notes
    -----
    Membership and decision are written in one transaction, so a request
    cannot end up marked approved with no membership behind it -- which
    would look decided to both parties while the requester still could not
    post, with nothing left in the queue to explain why.

    Unlike `goats_tom.antares_membership.approve_join_request`, nothing is
    added to a `django.contrib.auth.models.Group` here. This grant is about
    credentials, not data; target visibility stays with TOM's own sharing.
    """
    if join_request.status != TNSGroupJoinRequest.STATUS_PENDING:
        raise TNSJoinRequestError("That request has already been decided.")

    with transaction.atomic():
        membership, _ = TNSGroupMembership.objects.update_or_create(
            tns_group=join_request.tns_group,
            user=join_request.requester,
            defaults={"granted_by": decided_by},
        )
        join_request.status = TNSGroupJoinRequest.STATUS_APPROVED
        join_request.decided_by = decided_by
        join_request.decided_at = timezone.now()
        join_request.save(update_fields=["status", "decided_by", "decided_at"])

    logger.info(
        "Approved TNS join request id=%s (%s -> %s).",
        join_request.pk,
        join_request.requester.username,
        join_request.tns_group.name,
    )
    _notify(
        join_request.requester,
        label="TNS group request approved",
        message=(
            f"You can now post to TNS through '{join_request.tns_group.name}'."
        ),
        color="success",
    )
    return membership


def deny_join_request(join_request, decided_by):
    """Deny a pending request, keeping the record.

    Parameters
    ----------
    join_request : `goats_tom.models.TNSGroupJoinRequest`
        The pending request.
    decided_by : `django.contrib.auth.models.User`
        Who is denying it.

    Returns
    -------
    `goats_tom.models.TNSGroupJoinRequest`
        The updated request.

    Raises
    ------
    TNSJoinRequestError
        If the request is not pending.

    Notes
    -----
    Kept rather than deleted, so the owner can see they have already
    answered and the requester can see their request was decided rather
    than lost. The pending-only constraint means keeping it does not
    prevent a later re-request.
    """
    if join_request.status != TNSGroupJoinRequest.STATUS_PENDING:
        raise TNSJoinRequestError("That request has already been decided.")

    join_request.status = TNSGroupJoinRequest.STATUS_DENIED
    join_request.decided_by = decided_by
    join_request.decided_at = timezone.now()
    join_request.save(update_fields=["status", "decided_by", "decided_at"])

    logger.info(
        "Denied TNS join request id=%s (%s -> %s).",
        join_request.pk,
        join_request.requester.username,
        join_request.tns_group.name,
    )
    _notify(
        join_request.requester,
        label="TNS group request declined",
        message=(
            f"Your request to post through '{join_request.tns_group.name}' "
            "was not approved."
        ),
        color="secondary",
    )
    return join_request


def revoke_membership(membership) -> None:
    """Withdraw a member's permission to post through a group.

    Parameters
    ----------
    membership : `goats_tom.models.TNSGroupMembership`
        The membership to remove.

    Notes
    -----
    Takes effect on the next submission rather than retroactively, which is
    the only thing it could do -- anything already sent is on TNS and is
    the owner's to retract there. What the row's removal guarantees is that
    no *further* post goes out under the owner's bot: the middleware
    resolves the option against live membership on every request (see
    `resolve_posting_option`), so a session that still has the key selected
    falls back to whatever the user does hold.

    The member is told, because otherwise the first they learn of it is a
    submission page that has quietly changed which bot it will post as.
    """
    user = membership.user
    group = membership.tns_group
    membership.delete()

    logger.info(
        "Revoked TNS posting access for %s in %s.", user.username, group.name
    )
    _notify(
        user,
        label="TNS group access removed",
        message=(
            f"Your access to post to TNS through '{group.name}' has been "
            "removed."
        ),
        color="secondary",
    )
