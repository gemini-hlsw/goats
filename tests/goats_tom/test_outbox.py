"""Tests for `goats_tom.outbox`."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from goats_tom.models import OutgoingEmail
from goats_tom.outbox import queue_email, site_url
from goats_tom.tasks import send_email

CONTEXT = {
    "notification": SimpleNamespace(title="Hello", message="A message.", detail=""),
    "action_url": "",
    "inbox_url": "",
}


def _queue(to="ada@example.org"):
    return queue_email(to, "Hello", "notifications/email", CONTEXT)


@pytest.mark.django_db
def test_renders_both_parts_with_the_subject_prefix():
    email = _queue()

    assert email.to == "ada@example.org"
    assert email.subject == "[GOATS] Hello"
    assert "A message." in email.body
    assert "<p" in email.html and "A message." in email.html
    assert email.sent_at is None


@pytest.mark.django_db
def test_queues_the_email_once_the_transaction_commits(
    django_capture_on_commit_callbacks,
):
    with patch.object(send_email, "send") as send:
        with django_capture_on_commit_callbacks() as callbacks:
            email = _queue()
            send.assert_not_called()

        for callback in callbacks:
            callback()

    send.assert_called_once_with(email.pk)


@pytest.mark.django_db
def test_a_down_broker_leaves_the_email_for_the_sweep(
    django_capture_on_commit_callbacks,
):
    with patch.object(send_email, "send", side_effect=RuntimeError("no broker")):
        with django_capture_on_commit_callbacks(execute=True):
            email = _queue()

    email.refresh_from_db()
    assert email.sent_at is None


@pytest.mark.django_db
def test_nothing_is_queued_without_an_address():
    assert _queue(to="") is None
    assert not OutgoingEmail.objects.exists()


@pytest.mark.django_db
@override_settings(GOATS_SEND_EMAIL=False)
def test_nothing_is_queued_with_email_off():
    assert _queue() is None
    assert not OutgoingEmail.objects.exists()


@override_settings(GOATS_SITE_URL="https://goats.example.org/")
def test_site_url_makes_a_path_absolute():
    assert site_url("/notifications/") == "https://goats.example.org/notifications/"


@override_settings(GOATS_SITE_URL="")
def test_site_url_is_empty_without_a_site_url():
    assert site_url("/notifications/") == ""
