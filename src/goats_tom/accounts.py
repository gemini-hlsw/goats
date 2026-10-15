"""Requests an administrator decides: a new account, or a password reset."""

__all__ = [
    "AccountRequestError",
    "create_account_request",
    "approve_account_request",
    "deny_account_request",
    "request_password_reset",
    "approve_password_reset",
    "deny_password_reset",
    "password_change_required",
    "complete_password_change",
]

import logging
from collections.abc import Iterable

from django.contrib.auth.models import Group, User
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from goats_tom.models import AccountRequest, PasswordResetRequest
from goats_tom.notifications import notify, resolve
from goats_tom.outbox import queue_email

logger = logging.getLogger(__name__)


TEMPORARY_PASSWORD_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
"""Characters of a temporary password, without look-alikes such as 0/O or 1/l."""


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
    record : `AccountRequest` or `PasswordResetRequest`
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


def request_password_reset(username: str) -> PasswordResetRequest | None:
    """Ask the administrators to reset the password of `username`.

    Parameters
    ----------
    username : str
        The account's username.

    Returns
    -------
    `PasswordResetRequest` or None
        The pending request, or `None` if there is no such active account or
        one is already pending.
    """
    user = User.objects.filter(username=username, is_active=True).first()
    if user is None:
        return None
    try:
        with transaction.atomic():
            reset_request = PasswordResetRequest.objects.create(user=user)
            notify(
                User.objects.filter(is_superuser=True),
                "password.reset_requested",
                actor=user,
                subject=reset_request,
                reset_request=reset_request,
            )
    except IntegrityError:
        # One is already pending.
        return None
    logger.info("Password reset requested for %s.", username)
    return reset_request


def approve_password_reset(
    reset_request: PasswordResetRequest, decided_by: User
) -> str:
    """Give the account a temporary password it must change at the next sign-in.

    Parameters
    ----------
    reset_request : `PasswordResetRequest`
        The pending request.
    decided_by : `User`
        The administrator approving it.

    Returns
    -------
    str
        The temporary password, for the administrator to pass on.

    Raises
    ------
    AccountRequestError
        If it has already been decided.
    """
    password = get_random_string(12, TEMPORARY_PASSWORD_CHARS)
    with transaction.atomic():
        _decide(reset_request, PasswordResetRequest.STATUS_APPROVED, decided_by)
        user = reset_request.user
        user.set_password(password)
        user.save(update_fields=["password"])
        resolve(reset_request)
    logger.info(
        "Password reset of %s approved by %s.", user.username, decided_by.username
    )
    return password


def deny_password_reset(
    reset_request: PasswordResetRequest, decided_by: User
) -> PasswordResetRequest:
    """Deny a password reset, leaving the password as it is.

    Parameters
    ----------
    reset_request : `PasswordResetRequest`
        The pending request.
    decided_by : `User`
        The administrator denying it.

    Returns
    -------
    `PasswordResetRequest`
        The denied request.

    Raises
    ------
    AccountRequestError
        If it has already been decided.
    """
    with transaction.atomic():
        _decide(reset_request, PasswordResetRequest.STATUS_DENIED, decided_by)
        resolve(reset_request)
    logger.info(
        "Password reset of %s denied by %s.",
        reset_request.user.username,
        decided_by.username,
    )
    return reset_request


def password_change_required(user: User) -> bool:
    """Whether `user` signs in with a temporary password they must change.

    Parameters
    ----------
    user : `User`
        The account.

    Returns
    -------
    bool
        `True` while an approved reset has not been followed by a new password.
    """
    return PasswordResetRequest.objects.filter(
        user=user, status=PasswordResetRequest.STATUS_APPROVED
    ).exists()


def complete_password_change(user: User) -> None:
    """Record that `user` replaced their temporary password.

    Parameters
    ----------
    user : `User`
        The account.
    """
    PasswordResetRequest.objects.filter(
        user=user, status=PasswordResetRequest.STATUS_APPROVED
    ).update(status=PasswordResetRequest.STATUS_COMPLETED)
