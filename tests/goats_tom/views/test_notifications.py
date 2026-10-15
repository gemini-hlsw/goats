"""Tests for the notification inbox views and the navbar bell."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from goats_tom.models import Notification
from goats_tom.templatetags.notifications_extras import short_time
from goats_tom.tests.factories import UserFactory


def _notification(recipient, **fields) -> Notification:
    defaults = {
        "kind": "tns.join_denied",
        "title": "TNS group request declined",
        "message": "Your request was not approved.",
    }
    return Notification.objects.create(recipient=recipient, **{**defaults, **fields})


@pytest.fixture
def user(client):
    user = UserFactory()
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_the_inbox_lists_only_the_users_own(client, user):
    _notification(user, title="Mine")
    _notification(UserFactory(), title="Someone else's")

    response = client.get(reverse("notifications"))

    assert response.status_code == 200
    assert b"Mine" in response.content
    assert b"Someone else" not in response.content


@pytest.mark.django_db
def test_the_inbox_requires_login(client):
    response = client.get(reverse("notifications"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.django_db
def test_opening_marks_read_and_follows_the_link(client, user):
    notification = _notification(user, url="/targets/")

    response = client.get(reverse("notification-open", args=[notification.pk]))

    assert response.status_code == 302
    assert response["Location"] == "/targets/"
    notification.refresh_from_db()
    assert notification.is_read


@pytest.mark.django_db
def test_opening_without_a_link_goes_to_the_inbox(client, user):
    notification = _notification(user)

    response = client.get(reverse("notification-open", args=[notification.pk]))

    assert response["Location"] == reverse("notifications")


@pytest.mark.django_db
def test_an_offsite_link_is_not_followed(client, user):
    notification = _notification(user, url="https://evil.example.org/")

    response = client.get(reverse("notification-open", args=[notification.pk]))

    assert response["Location"] == reverse("notifications")


@pytest.mark.django_db
def test_another_users_notification_is_404(client, user):
    notification = _notification(UserFactory())

    response = client.get(reverse("notification-open", args=[notification.pk]))

    assert response.status_code == 404
    notification.refresh_from_db()
    assert not notification.is_read


@pytest.mark.django_db
def test_mark_all_read(client, user):
    _notification(user)
    _notification(user)
    theirs = _notification(UserFactory())

    response = client.post(reverse("notifications-read-all"))

    assert response.status_code == 302
    assert not Notification.objects.filter(recipient=user, read_at__isnull=True).exists()
    theirs.refresh_from_db()
    assert not theirs.is_read


@pytest.mark.django_db
def test_mark_all_read_is_post_only(client, user):
    assert client.get(reverse("notifications-read-all")).status_code == 405


@pytest.mark.django_db
def test_the_bell_shows_the_unread_count(client, user):
    _notification(user, title="Unread one")
    _notification(user, title="Read one", read_at=timezone.now())

    response = client.get(reverse("notifications"))

    content = response.content.decode()
    assert 'id="notificationBadge"' in content
    assert ">1</span>" in content
    assert "Unread one" in content


@pytest.mark.django_db
def test_the_bell_caps_the_count_at_nine(client, user):
    for _ in range(12):
        _notification(user)

    content = client.get(reverse("notifications")).content.decode()

    assert ">9+</span>" in content


def _bell(content: str) -> str:
    return content.split('id="notificationList"')[1].split('id="notificationEmpty"')[0]


@pytest.mark.django_db
def test_mark_all_read_is_offered_only_while_something_is_unread(client, user):
    _notification(user)
    assert b"Mark all as read" in client.get(reverse("notifications")).content

    Notification.objects.update(read_at=timezone.now())
    assert b"Mark all as read" not in client.get(reverse("notifications")).content


@pytest.mark.django_db
def test_the_inbox_keeps_what_fell_off_the_bell(client, user):
    _notification(user, title="Oldest", detail="Reason given")
    for _ in range(10):
        _notification(user)

    page = client.get(reverse("notifications")).content.decode()

    assert "Oldest" not in _bell(page)
    history = page.split('id="notificationHistory"')[1]
    assert "Oldest" in history
    assert "Reason given" in history


@pytest.mark.django_db
def test_the_inbox_shows_the_kind_icon_in_its_own_column(client, user):
    _notification(user, kind="tns.join_requested")

    page = client.get(reverse("notifications")).content.decode()
    history = page.split('id="notificationHistory"')[1]

    assert re.search(
        r'<td class="notification-history-kind[^"]*"><i class="[^"]*fa-user-clock[^"]*kind-warning',
        history,
    )


@pytest.mark.django_db
def test_bell_rows_show_the_kind_icon_and_short_time(client, user):
    _notification(user, kind="tns.join_requested")

    bell = _bell(client.get(reverse("notifications")).content.decode())

    assert re.search(r'notification-kind kind-warning"[^>]*><i class="[^"]*fa-user-clock', bell)
    assert ">now</time>" in bell


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=20), "now"),
        (timedelta(minutes=5), "5m"),
        (timedelta(hours=3), "3h"),
        (timedelta(days=2), "2d"),
    ],
)
def test_short_time(age, expected):
    now = timezone.now()

    assert short_time(now - age, now) == expected


def test_short_time_shows_the_date_after_a_week():
    now = datetime(2026, 10, 9, 12, tzinfo=UTC)

    assert short_time(datetime(2026, 9, 8, 12, tzinfo=UTC), now) == "8 Sep"
    assert short_time(datetime(2025, 9, 8, 12, tzinfo=UTC), now) == "8 Sep 2025"
