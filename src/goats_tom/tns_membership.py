"""Join requests, memberships and posting options for shared TNS groups.

Kept out of the views so the state changes are testable on their own and one
place knows how a request becomes a membership. Views handle HTTP and
permissions; this module handles what happens.

`posting_options` is the exception to that split: every other question here is
about *permission*, that one about which credentials a request goes out under.
Both `goats_tom.middleware.tns` and `goats_tom.views.tns_report` call it, so
the page can never offer a choice the middleware would refuse.
"""

__all__ = [
    "TNSJoinRequestError",
    "PostingOption",
    "owned_groups",
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
from django.db.models.functions import Lower
from django.utils import timezone

from goats_tom.models import (
    TNSGroup,
    TNSGroupJoinRequest,
    TNSGroupMembership,
)
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)


class TNSJoinRequestError(Exception):
    """Raised when a join request or decision cannot proceed."""


@dataclass(frozen=True)
class PostingOption:
    """One set of TNS credentials a user may submit with.

    An option is a **bot**, not a group: choosing it decides whose credentials
    go out, and the groups that bot may file under then populate `tom_tns`'s
    "Reporting group" field, which is where the second choice is made.

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
        The `goats_tom.models.TNSGroup` rows this option may file under. Every
        live group for the user's own bot; only the granted ones for somebody
        else's, which stops a grant on one group widening to the others.
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
        The author list is per-group but the group is chosen after the page
        loads, so a single pre-filled value would go stale on switching.
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
        The recipient. Addressed privately, since these name other users and
        reveal who posts through whose bot.
    label : str
        Notification heading.
    message : str
        Notification body. Plain text, never HTML, since it interpolates a
        username.
    color : str, optional
        Bootstrap colour scheme.
    autohide : bool, optional
        Whether the toast dismisses itself. `False` when the recipient has to
        act, so it cannot vanish while they look elsewhere.

    Notes
    -----
    Deferred with `transaction.on_commit`, so nobody is told about a change
    that rolls back. Failures are logged and swallowed: an unreachable
    channel layer must not fail the operation that triggered it.
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
                "Failed to notify user %s; the underlying change was still saved.",
                getattr(user, "username", None),
            )

    transaction.on_commit(_send)


def owned_groups(user):
    """The user's own groups that are still named on their credentials.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The credential owner.

    Returns
    -------
    `django.db.models.QuerySet`
        `TNSGroup` rows owned by `user`, ordered by name.

    Notes
    -----
    Shared by the page that renders the sharing settings and the endpoint
    that saves them, so the two can never disagree about which rows are
    editable: a group the page could not offer cannot be reached by a forged
    primary key either.

    Every row counts. There is no second list of names to agree with, which
    is the point of holding groups as rows: the owner adds and removes them
    here, and a rename keeps the memberships hanging off the row.

    Ordered case-insensitively, because the database's default collation
    compares bytes: it puts every capitalised name before every lowercase
    one, so "GOTO" landed above "Gemini" in a list a person reads.
    """
    return TNSGroup.objects.order_by(Lower("name")).filter(owner=user)


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
    A `TNSGroup` outlives the credentials it describes on purpose, so "opted
    in" and "usable" are different questions and the `tnslogin__isnull`
    filter answers the second.
    """
    return (
        TNSGroup.objects.filter(allow_join_requests=True)
        .exclude(owner__tnslogin__isnull=True)
        .select_related("owner", "owner__tnslogin")
        .order_by(Lower("name"))
    )


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

    pending_groups = TNSGroupJoinRequest.objects.filter(
        requester=user, status=TNSGroupJoinRequest.STATUS_PENDING
    ).values("tns_group_id")
    return (
        shareable_groups()
        .exclude(owner=user)
        .exclude(memberships__user=user)
        .exclude(pk__in=pending_groups)
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
    One option per *bot*: three groups from the same colleague are one entry
    with all three offered in Reporting group. Own credentials come first, so
    they are the default. A membership whose owner has deleted their
    credentials or dropped the group is skipped rather than offered.
    """
    if user is None or not user.is_authenticated:
        return []

    options: list[PostingOption] = []
    own_login = getattr(user, "tnslogin", None)

    if own_login is not None:
        own_groups = tuple(owned_groups(user))
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
        by_owner.setdefault(group.owner_id, []).append(group)

    for groups in by_owner.values():
        owner = groups[0].owner
        login = owner.tnslogin
        # Full name only: a username is half of a login credential, so an
        # owner without one shows as the bot alone.
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
    This is the authorisation check, not a convenience lookup. The key comes
    from the session or a form field, so it is matched against the
    freshly-computed list of what the user holds rather than trusted.

    Falling back rather than raising is deliberate: access can be revoked
    between choosing an option and using it, and posting as something they do
    still hold beats erroring out mid-submission.
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
    Both these checks and the partial unique constraint on pending requests
    exist on purpose: the checks give a readable error, the constraint closes
    the race between two rapid submissions.
    """
    if requester is None or not requester.is_authenticated:
        raise TNSJoinRequestError("You must be signed in to request access.")

    if tns_group.owner_id == requester.pk:
        raise TNSJoinRequestError("You already own this group.")

    if not tns_group.allow_join_requests:
        raise TNSJoinRequestError("That group is not accepting requests at the moment.")

    if TNSGroupMembership.objects.filter(tns_group=tns_group, user=requester).exists():
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
        # Somebody is waiting on the owner, so it stays until dismissed.
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
    cannot end up approved with no membership behind it -- decided to both
    parties while the requester still cannot post.

    Nothing is added to a `django.contrib.auth.models.Group`: this grant is
    about credentials, not data, and target visibility stays with TOM.
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
        message=(f"You can now post to TNS through '{join_request.tns_group.name}'."),
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
    Kept rather than deleted, so both sides can see it was answered. The
    pending-only constraint means keeping it still allows a re-request.
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
        # Not grey: this answers something the reader asked for.
        color="info",
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
    Takes effect on the next submission, not retroactively -- anything already
    sent is the owner's to retract on TNS. What it guarantees is that no
    *further* post goes out under the bot: `resolve_posting_option` re-checks
    live membership, so a session holding the key falls back.

    The member is told, since otherwise they first learn of it from a page
    that has quietly changed which bot it posts as.
    """
    user = membership.user
    group = membership.tns_group
    membership.delete()

    logger.info("Revoked TNS posting access for %s in %s.", user.username, group.name)
    _notify(
        user,
        label="TNS group access removed",
        message=(
            f"Your access to post to TNS through '{group.name}' has been removed."
        ),
        # Heavier than a decline: this takes away access already held.
        color="warning",
    )
