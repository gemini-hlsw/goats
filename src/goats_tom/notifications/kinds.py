"""Every kind of notification GOATS sends, in one registry.

A kind decides what a notification says and how it is delivered. Adding a new
event means registering one `NotificationKind` here; `notify` does the rest.
"""

__all__ = ["Content", "NotificationKind", "get_kind", "actionable_kinds", "style"]

from collections.abc import Callable
from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class Content:
    """What a notification says, rendered once and stored on the row.

    Attributes
    ----------
    title : str
        Short heading.
    message : str
        One or two sentences, plain text.
    detail : str
        Optional longer explanation for the inbox page and the email.
    url : str
        Site-relative path to act on it, or empty.
    """

    title: str
    message: str
    detail: str = ""
    url: str = ""


@dataclass(frozen=True)
class NotificationKind:
    """How one kind of event is worded and delivered.

    Attributes
    ----------
    key : str
        Stored on `goats_tom.models.Notification.kind`.
    render : Callable[..., Content]
        Builds the content from the keyword context passed to `notify`.
    color : str
        Bootstrap colour of the toast and of the icon in the bell and inbox.
    actionable : bool
        Whether it asks the recipient to act. Actionable notifications stay on
        screen and are resolved for every recipient once someone acts.
    email : bool
        Whether it is also emailed.
    icon : str
        Font Awesome icon shown next to it in the bell and inbox.
    """

    key: str
    render: Callable[..., Content]
    color: str = "info"
    actionable: bool = False
    email: bool = True
    icon: str = "fa-bell"


def _name(user) -> str:
    """Name `user` as GOATS shows them to others, never by username."""
    # Deferred: `custom_filters` imports the views, which import this module.
    from goats_tom.templatetags.custom_filters import (  # noqa: PLC0415
        display_name as _display_name,
    )

    return _display_name(user)


def _tns_join_requested(join_request) -> Content:
    group = join_request.tns_group
    detail = (
        "If you approve, reports and classifications they submit for this group "
        "are sent to TNS with your bot credentials and attributed to your bot."
    )
    if join_request.message:
        detail += f"\n\nTheir message:\n{join_request.message}"
    return Content(
        title="TNS group request",
        message=(
            f"{_name(join_request.requester)} requested access to report under "
            f"your TNS group '{group.name}'."
        ),
        detail=detail,
        # The query lets the page say when the request was already decided;
        # the fragment scrolls to its row while it is pending.
        url=(
            reverse("user-tns-login", kwargs={"pk": group.owner_id})
            + f"?request={join_request.pk}#join-request-{join_request.pk}"
        ),
    )


def _tns_join_approved(join_request) -> Content:
    group = join_request.tns_group
    return Content(
        title="TNS group request approved",
        message=f"You can now report to TNS through '{group.name}'.",
        detail=(
            f"Submissions for this group use {_name(group.owner)}'s bot "
            "credentials and TNS attributes them to that bot. Check the author "
            "list on the form before submitting."
        ),
        url=reverse("targets:list"),
    )


def _tns_join_denied(join_request) -> Content:
    return Content(
        title="TNS group request declined",
        message=(
            f"Your request to report through '{join_request.tns_group.name}' "
            "was not approved."
        ),
        detail="Contact the group's owner if you think this is a mistake.",
    )


def _tns_membership_revoked(tns_group) -> Content:
    return Content(
        title="TNS group access removed",
        message=f"Your access to report to TNS through '{tns_group.name}' was removed.",
    )


_KINDS: dict[str, NotificationKind] = {
    kind.key: kind
    for kind in (
        NotificationKind(
            "tns.join_requested",
            _tns_join_requested,
            "warning",
            actionable=True,
            icon="fa-user-clock",
        ),
        NotificationKind(
            "tns.join_approved", _tns_join_approved, "success", icon="fa-circle-check"
        ),
        NotificationKind(
            "tns.join_denied", _tns_join_denied, "secondary", icon="fa-circle-xmark"
        ),
        # Heavier than a decline: this takes away access already held.
        NotificationKind(
            "tns.membership_revoked",
            _tns_membership_revoked,
            "danger",
            icon="fa-user-minus",
        ),
    )
}


def get_kind(key: str) -> NotificationKind:
    """Look up a registered kind.

    Parameters
    ----------
    key : str
        The kind's key.

    Returns
    -------
    NotificationKind
        The registered kind.

    Raises
    ------
    ValueError
        If no kind has that key.
    """
    try:
        return _KINDS[key]
    except KeyError:
        raise ValueError(f"Unknown notification kind: {key!r}") from None


def actionable_kinds() -> list[str]:
    """Keys of every kind that asks its recipient to act."""
    return [key for key, kind in _KINDS.items() if kind.actionable]


def style(key: str) -> tuple[str, str]:
    """Icon and colour to show a notification of kind `key` with.

    Parameters
    ----------
    key : str
        The kind's key. An unknown one, e.g. a kind removed after rows were
        stored, gets a neutral bell.

    Returns
    -------
    tuple of str
        ``(icon, color)``.
    """
    kind = _KINDS.get(key)
    return (kind.icon, kind.color) if kind else ("fa-bell", "secondary")
