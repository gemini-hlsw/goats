"""Join request and membership transitions for ANTARES PI groups.

Kept out of the views so the state changes are testable on their own and so
there is one place that knows how a request becomes a membership. Views
handle HTTP and permissions; this module handles what actually happens.

Notification is deliberately *not* the mechanism here -- these functions
write to the database, and a PI's pending queue is rendered from those rows.
A real-time notification is sent as a convenience on top (see
`notify_pi_of_request`), so a PI who was offline when a request arrived still
sees it, rather than having missed the only signal.
"""

__all__ = [
    "JoinRequestError",
    "notify_pi_of_request",
    "notify_requester_of_decision",
    "requestable_pi_groups",
    "create_join_request",
    "approve_join_request",
    "deny_join_request",
    "revoke_membership",
]

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from goats_tom.models import (
    AntaresDashboardMembership,
    AntaresGroupJoinRequest,
    AntaresPIGroup,
)
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)


def _notify(user, label: str, message: str, color: str = "primary") -> None:
    """Send one notification to one user, after the current transaction commits.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The recipient. Addressed privately -- these messages name other
        users and reveal group activity, so they must not be broadcast to
        every connected client.
    label : str
        Notification heading.
    message : str
        Notification body. Plain text, never HTML: it interpolates a
        username, and keeping it plain removes any question of escaping
        user-controlled content.
    color : str, optional
        Bootstrap colour scheme.

    Notes
    -----
    Deferred with `transaction.on_commit` so a notification is never sent
    for a change that then rolls back -- otherwise a PI could be told about
    a request that does not exist. Outside an atomic block, Django runs the
    callback immediately, so this is also correct for unwrapped callers.

    Failures are logged and swallowed. Notification is a convenience layer
    over the database, which is the real source of truth for pending
    requests and memberships (see this module's docstring), so an
    unreachable channel layer must not fail the operation that triggered it.
    """

    def _send() -> None:
        try:
            NotificationInstance.create_and_send(
                label=label, message=message, color=color, user=user
            )
        except Exception:
            logger.exception(
                "Failed to notify user %s (%r); the underlying change was "
                "still saved.",
                getattr(user, "username", None),
                label,
            )

    transaction.on_commit(_send)


def notify_pi_of_request(join_request) -> None:
    """Tell a PI that someone has asked to join their group.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The newly-created request.
    """
    asked_for = "view access"
    if join_request.requested_save_targets:
        asked_for = "view access and permission to save targets"
    _notify(
        join_request.pi_group.pi,
        label="ANTARES access request",
        message=(
            f"{join_request.requester.username} has requested {asked_for} "
            f"for your ANTARES dashboard. Review it under "
            f"Alerts > Manage ANTARES Access."
        ),
        color="info",
    )


def notify_requester_of_decision(join_request, membership=None) -> None:
    """Tell a requester their request was approved or declined.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The decided request.
    membership : `goats_tom.models.AntaresDashboardMembership`, optional
        The resulting membership, when approved. Used to report what was
        actually granted, which may be narrower than what was asked for.
    """
    group_name = join_request.pi_group.group.name
    if join_request.status == AntaresGroupJoinRequest.STATUS_APPROVED:
        granted = "view access"
        if membership is not None and membership.can_save_targets:
            granted = "view access and permission to save targets"
        _notify(
            join_request.requester,
            label="ANTARES access approved",
            message=f"You were granted {granted} for {group_name}.",
            color="success",
        )
    else:
        _notify(
            join_request.requester,
            label="ANTARES access declined",
            message=f"Your request to join {group_name} was declined.",
            color="secondary",
        )


class JoinRequestError(Exception):
    """Raised when a join request can't be created or decided."""


def requestable_pi_groups(user):
    """PI groups `user` could ask to join.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The prospective member.

    Returns
    -------
    `django.db.models.QuerySet`
        PI groups excluding the user's own, any they are already a member
        of, and any with a request already pending. Filtering these out here
        rather than letting the form reject them afterwards means the user
        is never offered a choice that cannot succeed.
    """
    if user is None or not user.is_authenticated:
        return AntaresPIGroup.objects.none()

    return (
        AntaresPIGroup.objects.exclude(pi=user)
        .exclude(memberships__user=user)
        .exclude(
            join_requests__requester=user,
            join_requests__status=AntaresGroupJoinRequest.STATUS_PENDING,
        )
        .select_related("group", "pi")
        .order_by("group__name")
    )


def create_join_request(
    requester,
    pi_group,
    request_save_targets: bool = False,
    message: str = "",
) -> AntaresGroupJoinRequest:
    """Create a pending join request.

    Parameters
    ----------
    requester : `django.contrib.auth.models.User`
        The user asking for access.
    pi_group : `goats_tom.models.AntaresPIGroup`
        The group being requested.
    request_save_targets : bool, optional
        Whether they are also asking to save loci as targets. What is
        actually granted remains the PI's decision.
    message : str, optional
        Optional note to the PI.

    Returns
    -------
    `goats_tom.models.AntaresGroupJoinRequest`
        The created request.

    Raises
    ------
    JoinRequestError
        If the user is the group's PI, is already a member, or already has a
        pending request.

    Notes
    -----
    The checks here are re-checked by the database's partial unique
    constraint on pending requests (see `AntaresGroupJoinRequest.Meta`). Both
    exist on purpose: the checks give a readable error, and the constraint
    closes the race between two rapid submissions, which no amount of
    checking in Python can.
    """
    if requester is None or not requester.is_authenticated:
        raise JoinRequestError("You must be signed in to request access.")

    if pi_group.pi_id == requester.pk:
        raise JoinRequestError("You already own this group.")

    if AntaresDashboardMembership.objects.filter(
        pi_group=pi_group, user=requester
    ).exists():
        raise JoinRequestError("You are already a member of this group.")

    try:
        join_request = AntaresGroupJoinRequest.objects.create(
            requester=requester,
            pi_group=pi_group,
            requested_view_dashboard=True,
            requested_save_targets=request_save_targets,
            message=message,
        )
    except IntegrityError as exc:
        raise JoinRequestError(
            "You already have a pending request for this group."
        ) from exc

    notify_pi_of_request(join_request)
    return join_request


def approve_join_request(
    join_request,
    decided_by,
    grant_view: bool = True,
    grant_save: bool = False,
) -> AntaresDashboardMembership:
    """Approve a request and create the corresponding membership.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The pending request to approve.
    decided_by : `django.contrib.auth.models.User`
        Who is approving -- normally the group's PI.
    grant_view : bool, optional
        Whether to grant dashboard view access.
    grant_save : bool, optional
        Whether to grant target-saving access. Decided independently of what
        was requested, so a PI can approve a narrower set than asked for.

    Returns
    -------
    `goats_tom.models.AntaresDashboardMembership`
        The created or updated membership.

    Raises
    ------
    JoinRequestError
        If the request is not pending.

    Notes
    -----
    Does two things in one transaction: records the membership (which
    carries the two dashboard permissions) and adds the user to the
    underlying auth `Group`. Both are needed and for different reasons --
    the membership drives dashboard access, while the auth group is what TOM
    Toolkit shares targets with (see
    `goats_tom.models.AntaresPIGroup`). Doing them atomically means a
    half-approved state, where someone can see a dashboard but never
    receives the targets saved from it, can't occur.
    """
    if join_request.status != AntaresGroupJoinRequest.STATUS_PENDING:
        raise JoinRequestError("That request has already been decided.")

    with transaction.atomic():
        membership, _ = AntaresDashboardMembership.objects.update_or_create(
            pi_group=join_request.pi_group,
            user=join_request.requester,
            defaults={
                "can_view_dashboard": grant_view,
                "can_save_targets": grant_save,
                "granted_by": decided_by,
            },
        )
        join_request.requester.groups.add(join_request.pi_group.group)

        join_request.status = AntaresGroupJoinRequest.STATUS_APPROVED
        join_request.decided_by = decided_by
        join_request.decided_at = timezone.now()
        join_request.save(
            update_fields=["status", "decided_by", "decided_at"]
        )

    logger.info(
        "Approved ANTARES join request id=%s (%s -> %s) view=%s save=%s.",
        join_request.pk,
        join_request.requester.username,
        join_request.pi_group.group.name,
        grant_view,
        grant_save,
    )
    notify_requester_of_decision(join_request, membership=membership)
    return membership


def deny_join_request(join_request, decided_by) -> AntaresGroupJoinRequest:
    """Deny a pending request, keeping the record.

    Parameters
    ----------
    join_request : `goats_tom.models.AntaresGroupJoinRequest`
        The pending request to deny.
    decided_by : `django.contrib.auth.models.User`
        Who is denying it.

    Returns
    -------
    `goats_tom.models.AntaresGroupJoinRequest`
        The updated request.

    Raises
    ------
    JoinRequestError
        If the request is not pending.

    Notes
    -----
    The row is kept rather than deleted, so the PI can see they have already
    answered and the requester can see their request was decided rather than
    lost. The pending-only uniqueness constraint means keeping it doesn't
    prevent a later re-request.
    """
    if join_request.status != AntaresGroupJoinRequest.STATUS_PENDING:
        raise JoinRequestError("That request has already been decided.")

    join_request.status = AntaresGroupJoinRequest.STATUS_DENIED
    join_request.decided_by = decided_by
    join_request.decided_at = timezone.now()
    join_request.save(update_fields=["status", "decided_by", "decided_at"])

    logger.info(
        "Denied ANTARES join request id=%s (%s -> %s).",
        join_request.pk,
        join_request.requester.username,
        join_request.pi_group.group.name,
    )
    notify_requester_of_decision(join_request)
    return join_request


def revoke_membership(membership) -> None:
    """Remove a member's access entirely.

    Parameters
    ----------
    membership : `goats_tom.models.AntaresDashboardMembership`
        The membership to revoke.

    Notes
    -----
    Removes the auth group membership as well as the row, mirroring
    `approve_join_request` -- otherwise a revoked member would keep
    receiving targets shared with the PI's group despite having lost access
    to the dashboard those targets come from.

    Deliberately does not touch any `Target` the member already holds
    permissions on. Those were granted individually at save time and may be
    the basis of work in progress; silently withdrawing them is a
    destructive act that should be an explicit, separate decision rather
    than a side effect of revoking dashboard access.
    """
    user = membership.user
    group = membership.pi_group.group
    with transaction.atomic():
        membership.delete()
        user.groups.remove(group)

    logger.info(
        "Revoked ANTARES dashboard membership for %s in %s.",
        user.username,
        group.name,
    )
