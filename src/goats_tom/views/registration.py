"""Self-registration and administrator approval views."""

__all__ = [
    "register",
    "registration_requests",
    "decide_registration_request",
]

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from goats_tom.forms import RegistrationForm, selectable_groups
from goats_tom.models import RegistrationRequest
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)


def _notify_admins_of_registration(registration) -> None:
    """Tell every administrator that somebody has requested an account.

    Parameters
    ----------
    registration : `goats_tom.models.RegistrationRequest`
        The newly-created request.

    Notes
    -----
    Sent to each superuser individually rather than broadcast, since the
    message names a person and reveals that an account is pending -- not
    something every signed-in user should see.

    Deferred to `transaction.on_commit`, so an administrator is never told
    about a registration that then rolls back. Failures are logged and
    swallowed: the queue page is the source of truth, so an unreachable
    channel layer must not fail the registration itself.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    username = registration.user.username

    def _send() -> None:
        User = get_user_model()
        for admin in User.objects.filter(is_superuser=True, is_active=True):
            try:
                NotificationInstance.create_and_send(
                    label="Account request",
                    message=(
                        f"{username} has requested a GOATS account. Review it "
                        f"under Users -> Account requests."
                    ),
                    color="info",
                    user=admin,
                )
            except Exception:
                logger.exception(
                    "Failed to notify admin %s of registration by %s.",
                    admin.username,
                    username,
                )

    transaction.on_commit(_send)


def register(request: HttpRequest) -> HttpResponse:
    """Show and handle the public sign-up form.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered form, or a redirect to the login page after a successful
        request.

    Notes
    -----
    Open to anonymous visitors by design -- this is the sign-up page. The
    account it creates is inactive and cannot sign in until approved (see
    `goats_tom.forms.RegistrationForm.save`).

    An already-signed-in user is redirected away rather than shown the form,
    since registering while logged in is always a mistake.
    """
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                registration = RegistrationRequest.objects.create(
                    user=user, reason=form.cleaned_data.get("reason", "")
                )
                # Recorded, not applied. The user is inactive and holds no
                # group membership until an administrator grants it (see
                # `decide_registration_request`).
                registration.requested_groups.set(
                    form.cleaned_data.get("requested_groups") or []
                )
            _notify_admins_of_registration(registration)
            logger.info(
                "Account requested by %s, awaiting approval.", user.username
            )
            messages.success(
                request,
                "Your account request has been submitted. An administrator "
                "will review it, and you can sign in once it is approved.",
            )
            return redirect("login")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def registration_requests(request: HttpRequest) -> HttpResponse:
    """List account requests for an administrator.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object.

    Returns
    -------
    `HttpResponse`
        The rendered queue.

    Notes
    -----
    Superuser-only: approving an account grants access to the whole GOATS
    instance.
    """
    pending = (
        RegistrationRequest.objects.filter(
            status=RegistrationRequest.STATUS_PENDING
        )
        .select_related("user")
        .prefetch_related("requested_groups")
        .order_by("created_at")
    )
    decided = (
        RegistrationRequest.objects.exclude(
            status=RegistrationRequest.STATUS_PENDING
        )
        .select_related("user", "decided_by")
        .order_by("-decided_at")[:20]
    )
    return render(
        request,
        "registration/registration_requests.html",
        {"pending_requests": pending, "decided_requests": decided},
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def decide_registration_request(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve or reject one account request.

    Parameters
    ----------
    request : `HttpRequest`
        The HTTP request object. Reads `action`, either ``"approve"`` or
        ``"reject"``.
    pk : int
        Primary key of the request to decide.

    Returns
    -------
    `HttpResponse`
        Redirect back to the queue.

    Notes
    -----
    Approval activates the account and grants whichever groups the
    administrator ticked. The applicant's own selections arrive only as a
    request (see `goats_tom.models.RegistrationRequest.requested_groups`);
    what is granted here is what the administrator actually submitted, which
    may be fewer, more, or none of them. Reading the granted set from the
    POST rather than from the request row is what makes that possible.

    Groups are restricted to the same selectable set the forms offer, so a
    posted id cannot be used to slip somebody into an automatically-managed
    group -- an ANTARES PI group, for instance, whose membership is supposed
    to come with dashboard permissions attached.

    Activating is all that was holding the account back -- the user already
    chose their own password at registration, so there is nothing to send
    them and no email required.

    Rejection leaves the account inactive and keeps the record, so an
    administrator can see the request was answered rather than lost. The
    account is deliberately not deleted: deleting it would free the username
    for immediate re-registration, putting the same request back in the queue
    with no history of the earlier decision.
    """
    registration = get_object_or_404(
        RegistrationRequest.objects.select_related("user"), pk=pk
    )

    if registration.status != RegistrationRequest.STATUS_PENDING:
        messages.error(request, "That request has already been decided.")
        return redirect("registration-requests")

    action = request.POST.get("action")
    if action not in {"approve", "reject"}:
        messages.error(request, "Unknown action.")
        return redirect("registration-requests")

    approved = action == "approve"
    with transaction.atomic():
        registration.status = (
            RegistrationRequest.STATUS_APPROVED
            if approved
            else RegistrationRequest.STATUS_REJECTED
        )
        registration.decided_by = request.user
        registration.decided_at = timezone.now()
        registration.save(
            update_fields=["status", "decided_by", "decided_at"]
        )

        if approved:
            registration.user.is_active = True
            registration.user.save(update_fields=["is_active"])

            granted = selectable_groups().filter(
                pk__in=request.POST.getlist("grant_groups")
            )
            for group in granted:
                registration.user.groups.add(group)

    username = registration.user.username
    logger.info(
        "Account request for %s %s by %s.",
        username,
        "approved" if approved else "rejected",
        request.user.username,
    )
    if approved:
        messages.success(request, f"Approved the account for {username}.")
    else:
        messages.info(request, f"Rejected the account request from {username}.")

    return redirect("registration-requests")
