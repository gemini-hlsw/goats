"""Account requests an administrator decides."""

__all__ = [
    "AccountRequestError",
    "create_account_request",
    "approve_account_request",
    "deny_account_request",
]

import logging
from collections.abc import Iterable

from django.contrib.auth.models import Group, User
from django.db import models, transaction
from django.utils import timezone

from goats_tom.models import AccountRequest
from goats_tom.notifications import notify, resolve
from goats_tom.outbox import queue_email

logger = logging.getLogger(__name__)


class AccountRequestError(Exception):
    """Raised when a request cannot be decided."""


def create_account_request(
    user: User, affiliation: str = "", message: str = ""
) -> AccountRequest:
    """Save `user` inactive, open a pending request and tell the administrators.

    Parameters
    ----------
    user : `User`
        The unsaved account, with its password already set.
    affiliation : str, optional
        The applicant's institution, stored on their TOM profile.
    message : str, optional
        Note from the applicant to the administrators.

    Returns
    -------
    `AccountRequest`
        The pending request.
    """
    with transaction.atomic():
        user.is_active = False
        user.save()
        # TOM's `post_save` signal has created the profile.
        user.profile.affiliation = affiliation
        user.profile.save(update_fields=["affiliation"])
        account_request = AccountRequest.objects.create(
            user=user,
            username=user.username,
            full_name=user.get_full_name(),
            email=user.email,
            message=message,
        )
        notify(
            User.objects.filter(is_superuser=True),
            "account.requested",
            actor=user,
            subject=account_request,
            account_request=account_request,
        )
    logger.info("Account requested by %s.", user.username)
    return account_request


def _decide(record: models.Model, status: str, decided_by: User) -> None:
    """Record a decision on a request if it is still pending.

    Parameters
    ----------
    record : `AccountRequest`
        The request to decide.
    status : str
        The model's ``STATUS_APPROVED`` or ``STATUS_DENIED``.
    decided_by : `User`
        The administrator deciding it.

    Raises
    ------
    AccountRequestError
        If it has already been decided.
    """
    model = type(record)
    decided_at = timezone.now()
    # A conditional update rather than `select_for_update`, which SQLite ignores.
    decided = model.objects.filter(pk=record.pk, status=model.STATUS_PENDING).update(
        status=status, decided_by=decided_by, decided_at=decided_at
    )
    if not decided:
        raise AccountRequestError("That request has already been decided.")
    record.status = status
    record.decided_by = decided_by
    record.decided_at = decided_at


def approve_account_request(
    account_request: AccountRequest,
    decided_by: User,
    groups: Iterable[Group] = (),
) -> AccountRequest:
    """Activate the requested account, add it to `groups` and tell its owner.

    Parameters
    ----------
    account_request : `AccountRequest`
        The pending request.
    decided_by : `User`
        The administrator approving it.
    groups : iterable of `Group`, optional
        Groups to add the account to.

    Returns
    -------
    `AccountRequest`
        The approved request.

    Raises
    ------
    AccountRequestError
        If it has already been decided or its account was deleted.
    """
    if account_request.user is None:
        raise AccountRequestError("The account for that request no longer exists.")

    with transaction.atomic():
        _decide(account_request, AccountRequest.STATUS_APPROVED, decided_by)
        user = account_request.user
        user.is_active = True
        # It joins GOATS when approved, not when it asked to.
        user.date_joined = account_request.decided_at
        user.save(update_fields=["is_active", "date_joined"])
        user.groups.add(*groups)
        resolve(account_request)
        notify(
            user,
            "account.approved",
            actor=decided_by,
            subject=account_request,
            account_request=account_request,
        )

    logger.info("Account of %s approved by %s.", user.username, decided_by.username)
    return account_request


def deny_account_request(
    account_request: AccountRequest, decided_by: User
) -> AccountRequest:
    """Deny the request, delete its account and email the applicant.

    The request is kept as the record of the decision.

    Parameters
    ----------
    account_request : `AccountRequest`
        The pending request.
    decided_by : `User`
        The administrator denying it.

    Returns
    -------
    `AccountRequest`
        The denied request.

    Raises
    ------
    AccountRequestError
        If it has already been decided.
    """
    with transaction.atomic():
        _decide(account_request, AccountRequest.STATUS_DENIED, decided_by)
        # Frees the username and email for a new request.
        if account_request.user is not None:
            account_request.user.delete()
            account_request.user = None
        resolve(account_request)
        # An email rather than a notification: the account no longer exists.
        queue_email(
            account_request.email,
            "Your GOATS account request",
            "accounts/emails/denied",
            {"account_request": account_request},
        )

    logger.info(
        "Account request of %s denied by %s.",
        account_request.username,
        decided_by.username,
    )
    return account_request
