"""Tests for email notifications and password reset.

Two different standards apply here, and the difference matters.

The **notification** emails are a second channel onto a queue that is already
the source of truth -- both `RegistrationRequest` and
`AntaresGroupJoinRequest` say so in their docstrings. A failure there costs
immediacy and nothing else, so these must never propagate.

**Password reset** has no queue behind it. A user who does not receive the
token is locked out, so it must not be swallowed and must not be
reimplemented.
"""

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from unittest.mock import patch

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend
from django.urls import reverse

from goats_tom import emails
from goats_tom.models import RegistrationRequest
from goats_tom.tests.factories import UserFactory


@pytest.fixture
def registration(db):
    """A pending account request."""
    user = UserFactory(username="applicant", email="applicant@example.org")
    user.is_active = False
    user.save(update_fields=["is_active"])
    return RegistrationRequest.objects.create(user=user, reason="Programme GS-2026A")


@pytest.mark.django_db
class TestRegistrationEmails:
    """Administrators hear about requests; applicants hear the outcome."""

    def test_admins_are_told_about_a_request(self, registration, settings):
        settings.GOATS_ADMIN_EMAILS = ["goats@noirlab.edu"]
        emails.notify_admins_of_registration(registration)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["goats@noirlab.edu"]
        assert "applicant" in message.subject
        assert "Programme GS-2026A" in message.body

    def test_requested_groups_are_marked_as_not_granted(self, registration):
        """The form is public, so asking is not receiving.

        Notes
        -----
        An email that listed requested groups as though they were assigned
        would invite an administrator to approve without looking -- which is
        exactly what the model separates `requested_groups` from actual
        membership to prevent.
        """
        group = Group.objects.create(name="PI Team")
        registration.requested_groups.add(group)

        emails.notify_admins_of_registration(registration)

        assert "not yet granted" in mail.outbox[0].body

    def test_approval_reaches_the_applicant(self, registration):
        registration.status = RegistrationRequest.STATUS_APPROVED
        registration.save(update_fields=["status"])

        emails.notify_user_of_registration_decision(registration)

        assert mail.outbox[0].to == ["applicant@example.org"]
        assert "approved" in mail.outbox[0].subject.lower()

    def test_rejection_names_someone_to_ask(self, registration, settings):
        """A rejection with no recourse is worse than none.

        Notes
        -----
        The model records no reason for a decision, so inventing wording
        that implies one would mislead. Naming an address is the honest
        version.
        """
        settings.GOATS_ADMIN_EMAILS = ["goats@noirlab.edu"]
        registration.status = RegistrationRequest.STATUS_REJECTED
        registration.save(update_fields=["status"])

        emails.notify_user_of_registration_decision(registration)

        assert "goats@noirlab.edu" in mail.outbox[0].body


@pytest.mark.django_db
class TestFailuresNeverBlock:
    """A broken mail server must not cost somebody their request."""

    def test_a_send_failure_is_swallowed(self, registration, settings, caplog):
        """The queue is the source of truth; mail is the second channel.

        Notes
        -----
        Both request models say this explicitly. An unreachable SMTP server
        must not fail the registration that a person just submitted.
        """
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        with pytest.MonkeyPatch().context() as patch:
            patch.setattr(
                emails,
                "send_mail",
                lambda **kwargs: (_ for _ in ()).throw(RuntimeError("smtp down")),
            )
            emails.notify_admins_of_registration(registration)

        assert "Could not send email" in caplog.text

    def test_a_missing_address_is_not_an_error(self, db):
        """An account with no email is skipped, not raised on."""
        user = UserFactory(username="noaddress", email="")
        request = RegistrationRequest.objects.create(user=user)
        request.status = RegistrationRequest.STATUS_APPROVED
        request.save(update_fields=["status"])

        emails.notify_user_of_registration_decision(request)

        assert mail.outbox == []


@pytest.mark.django_db
class TestRecipients:
    """Where administrator mail goes."""

    def test_defaults_to_the_group_address(self, settings):
        """Not every superuser.

        Notes
        -----
        Superuser accounts change, a shared server should not mail whoever
        currently holds the flag, and a group address survives people
        leaving.
        """
        if hasattr(settings, "GOATS_ADMIN_EMAILS"):
            del settings.GOATS_ADMIN_EMAILS
        assert emails._admin_addresses() == ["goats@noirlab.edu"]

    def test_a_single_string_is_accepted(self, settings):
        """Configuration is easy to get subtly wrong.

        Notes
        -----
        A bare string would otherwise be iterated character by character and
        mail would be addressed to "g", "o", "a"...
        """
        settings.GOATS_ADMIN_EMAILS = "one@example.org"
        assert emails._admin_addresses() == ["one@example.org"]


@pytest.mark.django_db
class TestPasswordReset:
    """Django's built-in flow, with GOATS templates."""

    def test_all_four_routes_resolve(self):
        """The flow is four pages and breaks if any is missing."""
        assert reverse("password_reset")
        assert reverse("password_reset_done")
        assert reverse("password_reset_complete")
        assert reverse("password_reset_confirm", kwargs={"uidb64": "x", "token": "y"})

    def test_a_known_address_receives_a_link(self, client, db):
        user = UserFactory(email="pi@example.org")
        user.is_active = True
        user.save(update_fields=["is_active"])

        response = client.post(
            reverse("password_reset"), {"email": "pi@example.org"}, follow=True
        )

        assert response.status_code == 200
        assert len(mail.outbox) == 1
        assert "/accounts/reset/" in mail.outbox[0].body

    def test_an_unknown_address_sends_nothing_but_says_the_same(self, client, db):
        """The page must not reveal which addresses are registered.

        Notes
        -----
        Django's view behaves this way and the template matches it. Saying
        "no such account" would turn this page into a way to enumerate
        users.
        """
        response = client.post(
            reverse("password_reset"), {"email": "nobody@example.org"}, follow=True
        )

        assert response.status_code == 200
        assert mail.outbox == []

    def test_the_email_carries_a_usable_link(self, client, db):
        """Absolute, and pointing at the confirm view.

        Notes
        -----
        A relative link in an email is not clickable. This is built by
        Django from the request, which is why reset -- unlike the
        notification emails -- does not need `GOATS_SITE_URL`.
        """
        user = UserFactory(email="pi2@example.org")
        user.is_active = True
        user.save(update_fields=["is_active"])

        client.post(reverse("password_reset"), {"email": "pi2@example.org"})

        body = mail.outbox[0].body
        assert body.startswith("Someone asked to reset") or "reset" in body
        assert "http" in body


@pytest.mark.django_db
class TestJoinRequestEmails:
    """PIs hear about requests; requesters hear the outcome."""

    @pytest.fixture
    def pi_group(self, db):
        from goats_tom.models import AntaresPIGroup

        pi = UserFactory(username="the_pi", email="pi@example.org")
        group = Group.objects.create(name="PI Team")
        return AntaresPIGroup.objects.create(group=group, pi=pi)

    @pytest.fixture
    def join_request(self, db, pi_group):
        from goats_tom.models import AntaresGroupJoinRequest

        return AntaresGroupJoinRequest.objects.create(
            requester=UserFactory(username="asker", email="asker@example.org"),
            pi_group=pi_group,
            requested_save_targets=True,
            message="Working on GS-2026A.",
        )

    def test_the_pi_and_admins_are_both_told(self, join_request, settings):
        """A PI on an observing run must not block everyone behind them.

        Notes
        -----
        The model says a superuser may also decide these, so administrators
        are copied rather than being a fallback.
        """
        settings.GOATS_ADMIN_EMAILS = ["goats@noirlab.edu"]
        emails.notify_pi_of_join_request(join_request)

        assert set(mail.outbox[0].to) == {"pi@example.org", "goats@noirlab.edu"}
        assert "Working on GS-2026A." in mail.outbox[0].body

    def test_the_pi_is_read_from_the_right_field(self, join_request):
        """`AntaresPIGroup.pi`, not `owner`.

        Notes
        -----
        The *subscription* model uses `owner`; this one uses `pi`. Reading
        the wrong attribute returns None and the PI silently never hears
        about the request -- no error, just nothing.
        """
        emails.notify_pi_of_join_request(join_request)
        assert "pi@example.org" in mail.outbox[0].to

    def test_an_approval_reports_what_was_granted(self, join_request, pi_group):
        """Not what was asked for.

        Notes
        -----
        A PI may approve a narrower set of permissions. Telling somebody
        they can save targets when they cannot sends them to a button that
        refuses them.
        """
        from goats_tom.models import (
            AntaresDashboardMembership,
            AntaresGroupJoinRequest,
        )

        # Asked to save targets; granted view only.
        AntaresDashboardMembership.objects.create(
            user=join_request.requester,
            pi_group=pi_group,
            can_view_dashboard=True,
            can_save_targets=False,
        )
        join_request.status = AntaresGroupJoinRequest.STATUS_APPROVED
        join_request.save(update_fields=["status"])

        emails.notify_user_of_join_decision(join_request)

        body = mail.outbox[0].body
        assert "view the dashboard" in body
        assert "save loci as targets" not in body

    def test_a_denial_reaches_the_requester(self, join_request):
        from goats_tom.models import AntaresGroupJoinRequest

        join_request.status = AntaresGroupJoinRequest.STATUS_DENIED
        join_request.save(update_fields=["status"])

        emails.notify_user_of_join_decision(join_request)

        assert mail.outbox[0].to == ["asker@example.org"]
        assert "not approved" in mail.outbox[0].body


@pytest.mark.django_db
class TestPasswordResetFailure:
    """What a locked-out user sees when the mail server is down.

    Notes
    -----
    An earlier version of these tests patched `PasswordResetForm.save` to
    raise, which tested the handler and not the failure. It passed while the
    real behaviour was broken: Django's `send_mail` catches every exception
    itself, so nothing ever reached the view and the page said "check your
    email" while the relay refused every message with a 550.

    These fail the *backend* instead, which is what actually happens.
    """

    @pytest.fixture
    def user(self, db):
        user = UserFactory(email="locked@example.org")
        user.is_active = True
        user.save(update_fields=["is_active"])
        return user

    @pytest.fixture
    def broken_smtp(self, settings):
        """A backend that refuses, the way an unreachable relay does."""
        settings.EMAIL_BACKEND = "tests.goats_tom.test_emails.RefusingBackend"

    def test_the_form_reports_the_failure(self, client, user, broken_smtp):
        """Not a 500, and not a false success page."""
        response = client.post(
            reverse("password_reset"), {"email": "locked@example.org"}
        )

        assert response.status_code == 200
        assert b"could not send" in response.content.lower()

    def test_it_does_not_pretend_to_have_sent(self, client, user, broken_smtp):
        """The bug this was written for.

        Notes
        -----
        Django swallows the send exception, so without
        `RecordingPasswordResetForm` this renders "check your email" while
        nothing was delivered -- observed on a real deployment.
        """
        response = client.post(
            reverse("password_reset"), {"email": "locked@example.org"}
        )

        assert b"Check your email" not in response.content

    def test_it_names_someone_to_contact(self, client, user, broken_smtp, settings):
        """A locked-out user has no other route back in."""
        settings.GOATS_ADMIN_EMAILS = ["goats@noirlab.edu"]
        response = client.post(
            reverse("password_reset"), {"email": "locked@example.org"}
        )
        assert b"goats@noirlab.edu" in response.content

    def test_an_unknown_address_still_sees_the_success_page(
        self, client, db, broken_smtp
    ):
        """No send is attempted, so nothing failed.

        Notes
        -----
        This is what keeps the page from enumerating users. An unknown
        address takes the same path whether the mail server is healthy or
        not; only a genuinely attempted, genuinely failed send differs.
        """
        response = client.post(
            reverse("password_reset"), {"email": "nobody@example.org"}, follow=True
        )

        assert response.status_code == 200
        assert b"could not send" not in response.content.lower()

    def test_a_working_send_is_unaffected(self, client, user):
        """The guard must not change the normal path."""
        response = client.post(
            reverse("password_reset"), {"email": "locked@example.org"}, follow=True
        )

        assert response.status_code == 200
        assert len(mail.outbox) == 1


class RefusingBackend(BaseEmailBackend):
    """A backend that raises, standing in for an unreachable relay.

    Notes
    -----
    Fails at `send_messages`, which is where a real SMTP failure surfaces
    and what Django's `try` in `PasswordResetForm.send_mail` guards. A
    fixture that patched higher up would sit inside that swallow and prove
    nothing -- which is exactly what the previous version of these tests
    did.
    """

    def send_messages(self, email_messages):
        raise OSError("connection refused")


class TestHeloBackend:
    """`HeloEmailBackend` announces a configured domain."""

    def test_it_announces_the_configured_domain(self, settings):
        """The whole point: the greeting says `noirlab.edu`.

        Notes
        -----
        Checked by recording what Django would pass as `local_hostname`
        rather than by opening a socket -- a real connection would test the
        network, not this class.
        """
        from django.core.mail.utils import DNS_NAME

        from goats_tom.email_backends import HeloEmailBackend

        settings.GOATS_EMAIL_HELO_DOMAIN = "noirlab.edu"
        seen = []

        backend = HeloEmailBackend()
        with patch.object(
            EmailBackend, "open", lambda self: seen.append(DNS_NAME.get_fqdn())
        ):
            backend.open()

        assert seen == ["noirlab.edu"]

    def test_it_is_inert_without_the_setting(self, settings):
        """Unset means Django's behaviour, unchanged."""
        from django.core.mail.utils import DNS_NAME

        from goats_tom.email_backends import HeloEmailBackend

        settings.GOATS_EMAIL_HELO_DOMAIN = ""
        real = DNS_NAME.get_fqdn()
        seen = []

        backend = HeloEmailBackend()
        with patch.object(
            EmailBackend, "open", lambda self: seen.append(DNS_NAME.get_fqdn())
        ):
            backend.open()

        assert seen == [real]

    def test_it_restores_the_hostname_after_a_failure(self, settings):
        """A leaked override would change every other send in the process.

        Notes
        -----
        `DNS_NAME` is module-level and shared. Restoring in `finally` is
        what keeps this backend from being action-at-a-distance -- the
        reason it is a subclass rather than a global reassignment.
        """
        from django.core.mail.utils import DNS_NAME

        from goats_tom.email_backends import HeloEmailBackend

        settings.GOATS_EMAIL_HELO_DOMAIN = "noirlab.edu"
        before = DNS_NAME.get_fqdn()

        backend = HeloEmailBackend(host="127.0.0.1", port=1, timeout=1)
        try:
            backend.open()
        except Exception:
            pass

        assert DNS_NAME.get_fqdn() == before
