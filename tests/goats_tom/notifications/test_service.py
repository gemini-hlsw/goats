"""Tests for `goats_tom.notifications.service`."""

from unittest.mock import patch

import pytest
from django.db.models import QuerySet
from django.utils import timezone
from django.test import override_settings

from goats_tom.models import Notification
from goats_tom.tasks import send_notification_email
from goats_tom.notifications import (
    mark_all_read,
    mark_read,
    notify,
    resolve,
    serialize,
    unread_count,
)
from goats_tom.tests.factories import TNSGroupJoinRequestFactory, UserFactory

PUSH = "goats_tom.notifications.service.InboxUpdate.send"


def queue(**kwargs):
    return patch.object(send_notification_email, "send", **kwargs)


@pytest.fixture
def join_request():
    request = TNSGroupJoinRequestFactory(message="We are on the same programme.")
    request.tns_group.owner.email = "owner@example.org"
    request.tns_group.owner.save()
    return request


def _request_owner(join_request) -> list[Notification]:
    return notify(
        join_request.tns_group.owner,
        "tns.join_requested",
        actor=join_request.requester,
        subject=join_request,
        join_request=join_request,
    )


@pytest.mark.django_db
def test_notify_stores_the_rendered_content(join_request):
    [row] = _request_owner(join_request)

    assert row.recipient == join_request.tns_group.owner
    assert row.kind == "tns.join_requested"
    assert join_request.tns_group.name in row.message
    assert "same programme" in row.detail
    assert row.url == (
        f"/users/{join_request.tns_group.owner_id}/tns/"
        f"?request={join_request.pk}#join-request-{join_request.pk}"
    )
    assert row.actor == join_request.requester
    assert (row.subject_type.model_class(), row.subject_id) == (type(join_request), join_request.pk)
    assert not row.is_read


@pytest.mark.django_db
def test_notify_never_names_the_username(join_request):
    requester = join_request.requester
    requester.first_name, requester.last_name = "Ada", "Lovelace"
    requester.save()

    [row] = _request_owner(join_request)

    assert "Ada Lovelace" in row.message
    assert requester.username not in row.message


@pytest.mark.django_db
def test_notify_skips_inactive_and_duplicate_recipients(join_request):
    active = UserFactory()
    inactive = UserFactory(is_active=False)

    rows = notify(
        [active, active, inactive, None],
        "tns.membership_revoked",
        tns_group=join_request.tns_group,
    )

    assert [row.recipient for row in rows] == [active]


@pytest.mark.django_db
def test_unknown_kind_is_refused():
    with pytest.raises(ValueError, match="Unknown notification kind"):
        notify(UserFactory(), "no.such.kind")


@pytest.mark.django_db
def test_delivery_waits_for_commit(join_request, django_capture_on_commit_callbacks):
    with patch(PUSH) as push, queue() as queued:
        with django_capture_on_commit_callbacks() as callbacks:
            [row] = _request_owner(join_request)
            push.assert_not_called()

        for callback in callbacks:
            callback()

    push.assert_called_once_with(row.recipient_id, 1, serialize(row))
    queued.assert_called_once_with(row.pk)


@pytest.mark.django_db
def test_no_email_without_an_address(join_request, django_capture_on_commit_callbacks):
    join_request.tns_group.owner.email = ""
    join_request.tns_group.owner.save()

    with patch(PUSH), queue() as queued:
        with django_capture_on_commit_callbacks(execute=True):
            [row] = _request_owner(join_request)

    queued.assert_not_called()
    assert not row.email_pending


@pytest.mark.django_db
@override_settings(GOATS_EMAIL_NOTIFICATIONS=False)
def test_no_email_when_disabled(join_request, django_capture_on_commit_callbacks):
    with patch(PUSH), queue() as queued:
        with django_capture_on_commit_callbacks(execute=True):
            [row] = _request_owner(join_request)

    queued.assert_not_called()
    assert not row.email_pending


@pytest.mark.django_db
def test_delivery_failures_keep_the_notification(
    join_request, django_capture_on_commit_callbacks
):
    with (
        patch(PUSH, side_effect=RuntimeError("no channel layer")),
        queue(side_effect=RuntimeError("no broker")),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            _request_owner(join_request)

    # Still owed, so the periodic sweep queues it once the broker is back.
    assert Notification.objects.get().email_pending


@pytest.mark.django_db
def test_resolve_clears_only_actionable_notifications(
    join_request, django_capture_on_commit_callbacks
):
    [request_row] = _request_owner(join_request)
    [decision_row] = notify(
        join_request.requester,
        "tns.join_approved",
        subject=join_request,
        join_request=join_request,
    )

    with patch(PUSH) as push:
        with django_capture_on_commit_callbacks(execute=True):
            assert resolve(join_request) == 1

    request_row.refresh_from_db()
    decision_row.refresh_from_db()
    assert request_row.is_read
    assert not decision_row.is_read
    push.assert_called_once_with(request_row.recipient_id, 0, read_ids=[request_row.pk])


@pytest.mark.django_db
def test_mark_read_and_mark_all_read(join_request, django_capture_on_commit_callbacks):
    owner = join_request.tns_group.owner
    first = _request_owner(join_request)[0]
    notify(owner, "tns.membership_revoked", tns_group=join_request.tns_group)
    other = notify(UserFactory(), "tns.membership_revoked", tns_group=join_request.tns_group)

    with patch(PUSH):
        with django_capture_on_commit_callbacks(execute=True):
            mark_read(first)
        assert unread_count(owner) == 1

        with django_capture_on_commit_callbacks(execute=True):
            assert mark_all_read(owner) == 1

    assert unread_count(owner) == 0
    assert unread_count(other[0].recipient) == 1


@pytest.mark.django_db
def test_serialize_marks_actionable_as_sticky(join_request):
    [row] = _request_owner(join_request)

    data = serialize(row)

    assert data["color"] == "warning"
    assert data["autohide"] is False
    assert data["title"] == row.title


@pytest.mark.django_db
def test_serialize_survives_a_removed_kind():
    row = Notification.objects.create(
        recipient=UserFactory(), kind="gone.kind", title="Old", message="Still here."
    )

    assert serialize(row)["color"] == "secondary"
    assert serialize(row)["icon"] == "fa-bell"


@pytest.mark.django_db
def test_marking_read_pushes_the_read_ids(join_request, django_capture_on_commit_callbacks):
    owner = join_request.tns_group.owner
    first = _request_owner(join_request)[0]
    second = notify(owner, "tns.membership_revoked", tns_group=join_request.tns_group)[0]

    with patch(PUSH) as push:
        with django_capture_on_commit_callbacks(execute=True):
            mark_read(first)
        push.assert_called_once_with(owner.pk, 1, read_ids=[first.pk])

        push.reset_mock()
        with django_capture_on_commit_callbacks(execute=True):
            mark_all_read(owner)
        push.assert_called_once_with(owner.pk, 0, read_ids=[second.pk])


@pytest.mark.django_db
def test_mark_all_read_leaves_a_notification_created_meanwhile(join_request):
    owner = join_request.tns_group.owner
    [shown] = _request_owner(join_request)
    original = QuerySet.values_list
    arrived = []

    def values_list_then_arrive(self, *fields, **kwargs):
        result = list(original(self, *fields, **kwargs))
        if not arrived:
            arrived.extend(
                notify(owner, "tns.membership_revoked", tns_group=join_request.tns_group)
            )
        return result

    with patch.object(QuerySet, "values_list", values_list_then_arrive), patch(PUSH):
        assert mark_all_read(owner) == 1

    shown.refresh_from_db()
    arrived[0].refresh_from_db()
    assert shown.is_read
    assert not arrived[0].is_read


@pytest.mark.django_db
def test_serialize_carries_the_kind_icon(join_request):
    [row] = _request_owner(join_request)

    assert serialize(row)["icon"] == "fa-user-clock"
