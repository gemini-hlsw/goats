"""Tests for `goats_tom.tasks.send_email`."""

from unittest.mock import patch

import pytest
from django.core import mail
from dramatiq.middleware.time_limit import TimeLimitExceeded
from django.test import override_settings
from django.utils import timezone

from goats_tom.models import OutgoingEmail
from goats_tom.tasks import retry_emails, send_email
from goats_tom.tasks.send_email import MAX_ATTEMPTS, RETRY_AFTER


@pytest.fixture
def email():
    return OutgoingEmail.objects.create(
        to="ada@example.org",
        subject="[GOATS] TNS group request",
        body="Plain text.",
        html="<p>HTML.</p>",
    )


@pytest.mark.django_db
def test_sends_text_and_html(email):
    send_email.fn(email.pk)

    [sent] = mail.outbox
    assert sent.to == ["ada@example.org"]
    assert sent.subject == "[GOATS] TNS group request"
    assert sent.body == "Plain text."
    html, mimetype = sent.alternatives[0]
    assert (html, mimetype) == ("<p>HTML.</p>", "text/html")
    email.refresh_from_db()
    assert email.sent_at is not None


@pytest.mark.django_db
def test_the_body_is_not_kept_once_sent(email):
    send_email.fn(email.pk)

    email.refresh_from_db()
    assert (email.body, email.html) == ("", "")


@pytest.mark.django_db
def test_the_body_is_kept_for_a_retry_after_a_failure(email):
    with patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=OSError("SMTP down"),
    ):
        send_email.fn(email.pk)

    email.refresh_from_db()
    assert email.body == "Plain text."


@pytest.mark.django_db
def test_a_text_only_email_has_no_html_part(email):
    OutgoingEmail.objects.filter(pk=email.pk).update(html="")

    send_email.fn(email.pk)

    assert mail.outbox[0].alternatives == []


@pytest.mark.django_db
def test_a_retry_does_not_send_twice(email):
    send_email.fn(email.pk)
    send_email.fn(email.pk)

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_failed_send_releases_the_claim_for_the_sweep(email):
    with patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=OSError("SMTP down"),
    ):
        send_email.fn(email.pk)

    email.refresh_from_db()
    assert email.sent_at is None
    assert email.attempts == 1


@pytest.mark.django_db
def test_an_interrupted_send_is_left_for_the_sweep(email):
    with (
        patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=TimeLimitExceeded(),
        ),
        pytest.raises(TimeLimitExceeded),
    ):
        send_email.fn(email.pk)

    email.refresh_from_db()
    assert email.sent_at is None
    assert email.body == "Plain text."


@pytest.mark.django_db
def test_gives_up_after_the_last_attempt(email):
    OutgoingEmail.objects.filter(pk=email.pk).update(attempts=MAX_ATTEMPTS)

    send_email.fn(email.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_a_deleted_email_is_skipped():
    send_email.fn(123456)

    assert mail.outbox == []


@pytest.mark.django_db
def test_an_email_claimed_by_another_worker_is_skipped(email):
    OutgoingEmail.objects.filter(pk=email.pk).update(sent_at=timezone.now())

    send_email.fn(email.pk)

    assert mail.outbox == []


@pytest.mark.django_db
def test_the_claim_is_stored_before_sending(email):
    claimed_during_send = []

    def record(*args, **kwargs):
        claimed_during_send.append(
            OutgoingEmail.objects.get(pk=email.pk).sent_at is not None
        )
        return 1

    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=record):
        send_email.fn(email.pk)

    assert claimed_during_send == [True]


def _age(email, by=RETRY_AFTER):
    OutgoingEmail.objects.filter(pk=email.pk).update(
        created_at=timezone.now() - by - timezone.timedelta(seconds=1)
    )


@pytest.mark.django_db
def test_the_sweep_requeues_unsent_emails(email):
    _age(email)
    sent = OutgoingEmail.objects.create(
        to="b@example.org", subject="s", body="b", sent_at=timezone.now()
    )
    _age(sent)

    with patch.object(send_email, "send") as send:
        retry_emails.fn()

    send.assert_called_once_with(email.pk)


@pytest.mark.django_db
def test_the_sweep_leaves_recent_and_exhausted_emails(email):
    exhausted = OutgoingEmail.objects.create(
        to="b@example.org", subject="s", body="b", attempts=MAX_ATTEMPTS
    )
    _age(exhausted)

    with patch.object(send_email, "send") as send:
        retry_emails.fn()

    send.assert_not_called()


@pytest.mark.django_db
@override_settings(GOATS_SEND_EMAIL=False)
def test_the_sweep_does_nothing_with_email_off(email):
    _age(email)

    with patch.object(send_email, "send") as send:
        retry_emails.fn()

    send.assert_not_called()
