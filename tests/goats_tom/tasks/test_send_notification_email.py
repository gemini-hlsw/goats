"""Tests for `goats_tom.tasks.send_notification_email`."""

from unittest.mock import patch

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from goats_tom.models import Notification
from goats_tom.tasks import retry_notification_emails, send_notification_email
from goats_tom.tasks.send_notification_email import MAX_ATTEMPTS, RETRY_AFTER
from goats_tom.tests.factories import UserFactory


@pytest.fixture
def notification():
    return Notification.objects.create(
        recipient=UserFactory(email="ada@example.org"),
        kind="tns.join_requested",
        title="TNS group request",
        message="Somebody asked to report under your group.",
        detail="Line one.\nLine two.",
        url="/users/1/tns/",
        email_pending=True,
    )


@pytest.mark.django_db
def test_sends_text_and_html_with_absolute_links(notification):
    send_notification_email.fn(notification.pk)

    [email] = mail.outbox
    assert email.to == ["ada@example.org"]
    assert email.subject == "[GOATS] TNS group request"
    assert "http://testserver/users/1/tns/" in email.body
    assert "http://testserver/notifications/" in email.body
    html, mimetype = email.alternatives[0]
    assert mimetype == "text/html"
    assert "Line one.<br>Line two." in html
    notification.refresh_from_db()
    assert notification.emailed_at is not None


@pytest.mark.django_db
def test_a_retry_does_not_send_twice(notification):
    send_notification_email.fn(notification.pk)
    send_notification_email.fn(notification.pk)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(GOATS_SITE_URL="")
def test_links_are_left_out_without_a_site_url(notification):
    send_notification_email.fn(notification.pk)

    assert "/users/1/tns/" not in mail.outbox[0].body


@pytest.mark.django_db
def test_nothing_is_sent_without_an_address(notification):
    notification.recipient.email = ""
    notification.recipient.save()

    send_notification_email.fn(notification.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_a_failed_send_releases_the_claim_for_the_sweep(notification):
    with patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=OSError("SMTP down"),
    ):
        send_notification_email.fn(notification.pk)

    notification.refresh_from_db()
    assert notification.emailed_at is None
    assert notification.email_attempts == 1


@pytest.mark.django_db
def test_gives_up_after_the_last_attempt(notification):
    Notification.objects.filter(pk=notification.pk).update(email_attempts=MAX_ATTEMPTS)

    send_notification_email.fn(notification.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_a_notification_that_owes_no_email_is_not_sent(notification):
    Notification.objects.filter(pk=notification.pk).update(email_pending=False)

    send_notification_email.fn(notification.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_a_deleted_notification_is_skipped():
    send_notification_email.fn(123456)

    assert mail.outbox == []


@pytest.mark.django_db
def test_a_notification_claimed_by_another_worker_is_skipped(notification):
    Notification.objects.filter(pk=notification.pk).update(emailed_at=timezone.now())

    send_notification_email.fn(notification.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_the_claim_is_stored_before_sending(notification):
    claimed_during_send = []

    def record(*args, **kwargs):
        claimed_during_send.append(
            Notification.objects.get(pk=notification.pk).emailed_at is not None
        )
        return 1

    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=record):
        send_notification_email.fn(notification.pk)

    assert claimed_during_send == [True]


def _age(notification, by=RETRY_AFTER):
    Notification.objects.filter(pk=notification.pk).update(
        created_at=timezone.now() - by - timezone.timedelta(seconds=1)
    )


@pytest.mark.django_db
def test_the_sweep_requeues_owed_emails(notification):
    _age(notification)
    sent = Notification.objects.create(
        recipient=notification.recipient,
        kind="tns.join_denied",
        title="t",
        message="m",
        email_pending=True,
        emailed_at=timezone.now(),
    )
    _age(sent)

    with patch.object(send_notification_email, "send") as send:
        retry_notification_emails.fn()

    send.assert_called_once_with(notification.pk)


@pytest.mark.django_db
def test_the_sweep_leaves_recent_and_exhausted_emails(notification):
    exhausted = Notification.objects.create(
        recipient=notification.recipient,
        kind="tns.join_denied",
        title="t",
        message="m",
        email_pending=True,
        email_attempts=MAX_ATTEMPTS,
    )
    _age(exhausted)

    with patch.object(send_notification_email, "send") as send:
        retry_notification_emails.fn()

    send.assert_not_called()


@pytest.mark.django_db
@override_settings(GOATS_EMAIL_NOTIFICATIONS=False)
def test_the_sweep_does_nothing_with_email_off(notification):
    _age(notification)

    with patch.object(send_notification_email, "send") as send:
        retry_notification_emails.fn()

    send.assert_not_called()
