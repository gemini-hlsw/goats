"""Tests for personal groups, group filtering, and self-registration."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.forms import selectable_groups
from goats_tom.models import (
    AntaresPIGroup,
    AntaresStreamSubscription,
    PersonalGroup,
    RegistrationRequest,
)


@pytest.mark.django_db()
class TestPersonalGroupCreation:
    """Tests for `goats_tom.signals.ensure_user_has_a_group`.

    The signal defers its work to `transaction.on_commit`, which is what makes
    the membership survive TOM's ``save_m2m()``. Django never commits inside a
    test, so these tests use `django_capture_on_commit_callbacks` to run those
    callbacks explicitly -- without it the signal appears to do nothing.
    """

    def test_new_user_gets_a_linked_personal_group(
        self, django_capture_on_commit_callbacks
    ):
        """A new account gets a group, linked and joined."""
        with django_capture_on_commit_callbacks(execute=True):
            user = User.objects.create_user("fresh")
        personal = PersonalGroup.objects.filter(user=user).first()
        assert personal is not None
        assert personal.group.name == "user-fresh"
        assert user.groups.filter(pk=personal.group.pk).exists()

    def test_membership_survives_a_later_group_assignment(
        self, django_capture_on_commit_callbacks
    ):
        """A later groups.set() must not orphan the personal group.

        Regression test for the bug where TOM's user form ran
        ``user.save()`` then ``save_m2m()``, and the second call cleared the
        membership the signal had just added -- leaving an empty
        ``user-<name>`` group, and a duplicate ``user-<name>-2`` created on
        the user's next save.
        """
        with django_capture_on_commit_callbacks(execute=True):
            user = User.objects.create_user("formsaved")
        other = Group.objects.create(name="real-team")

        # What CustomUserCreationForm.save_m2m() effectively does.
        with django_capture_on_commit_callbacks(execute=True):
            user.groups.set([other])
            user.save()

        personal = PersonalGroup.objects.get(user=user)
        assert user.groups.filter(pk=personal.group.pk).exists()
        assert not Group.objects.filter(name="user-formsaved-2").exists()

    def test_no_duplicate_group_on_repeated_saves(
        self, django_capture_on_commit_callbacks
    ):
        """Repeated saves reuse the linked group instead of suffixing."""
        with django_capture_on_commit_callbacks(execute=True):
            user = User.objects.create_user("repeat")
        for _ in range(3):
            with django_capture_on_commit_callbacks(execute=True):
                user.save()
        assert PersonalGroup.objects.filter(user=user).count() == 1
        assert not Group.objects.filter(name__startswith="user-repeat-").exists()

    def test_name_collision_is_suffixed(
        self, django_capture_on_commit_callbacks
    ):
        """An unrelated group of the same name does not break account creation."""
        Group.objects.create(name="user-clash")
        with django_capture_on_commit_callbacks(execute=True):
            user = User.objects.create_user("clash")
        personal = PersonalGroup.objects.get(user=user)
        assert personal.group.name == "user-clash-2"
        assert user.groups.filter(pk=personal.group.pk).exists()

    def test_pi_keeps_both_groups(self, django_capture_on_commit_callbacks):
        """A PI has a personal group and their team group.

        "Just me" and "my team" are both useful choices on the observation
        form.
        """
        from goats_tom.models import AntaresKafkaLogin

        with django_capture_on_commit_callbacks(execute=True):
            pi = User.objects.create_user("pi_alice")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        names = set(pi.groups.values_list("name", flat=True))
        assert "user-pi_alice" in names
        assert "antares-pi_alice" in names

    def test_anonymous_placeholder_gets_no_group(
        self, django_capture_on_commit_callbacks
    ):
        """django-guardian's anonymous user is not a person.

        It lives in auth_user, so it looks like an account to any signal
        watching the user model -- but it must not appear in group pickers.
        guardian creates the row itself during migrations, so this fetches it
        rather than creating a duplicate.
        """
        anon, _ = User.objects.get_or_create(username="AnonymousUser")
        with django_capture_on_commit_callbacks(execute=True):
            anon.save()
        assert not PersonalGroup.objects.filter(user=anon).exists()
        assert not Group.objects.filter(name="user-AnonymousUser").exists()


@pytest.mark.django_db()
class TestSelectableGroups:
    """Tests for the filtered group picker."""

    def test_personal_groups_excluded(self, django_capture_on_commit_callbacks):
        """A user's own group is not offered as a manual choice."""
        with django_capture_on_commit_callbacks(execute=True):
            user = User.objects.create_user("someone")
        personal = PersonalGroup.objects.get(user=user)
        assert personal.group not in selectable_groups()

    def test_pi_groups_excluded(self):
        """ANTARES PI groups are granted by approval, not by ticking a box."""
        pi = User.objects.create_user("thepi")
        group = Group.objects.create(name="antares-thepi")
        AntaresPIGroup.objects.create(group=group, pi=pi)
        assert group not in selectable_groups()

    def test_ordinary_groups_included(self):
        """Real collaboration groups remain selectable."""
        group = Group.objects.create(name="my-collaboration")
        assert group in selectable_groups()

    def test_filtering_is_by_relation_not_name(self):
        """A group merely named like a personal one is still offered.

        Matching a ``user-`` prefix would hide legitimate groups.
        """
        group = Group.objects.create(name="user-facing-tools")
        assert group in selectable_groups()


@pytest.mark.django_db()
class TestRegistration:
    """Tests for self-registration and admin approval."""

    def test_registration_creates_inactive_user(self, client):
        """A new sign-up cannot sign in until approved."""
        response = client.post(
            reverse("register"),
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "password1": "sufficiently-long-pw-1",
                "password2": "sufficiently-long-pw-1",
                "affiliation": "Gemini Observatory",
                "first_name": "Test",
                "last_name": "User",
                "reason": "Programme GS-2026A-Q-1",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(username="newbie")
        assert not user.is_active
        request = RegistrationRequest.objects.get(user=user)
        assert request.status == RegistrationRequest.STATUS_PENDING
        assert request.reason == "Programme GS-2026A-Q-1"

    def test_field_order_puts_identity_before_credentials(self):
        """Affiliation is asked with the other identity questions.

        Django appends explicitly-declared fields after the model's own, which
        would put affiliation below the password boxes without an explicit
        `field_order`.
        """
        from goats_tom.forms import RegistrationForm

        names = list(RegistrationForm().fields)
        assert names.index("affiliation") < names.index("password1")
        assert names.index("email") < names.index("affiliation")

    def test_affiliation_is_required(self, client):
        """Registration without an affiliation is rejected."""
        client.post(
            reverse("register"),
            {
                "username": "noaffil",
                "email": "noaffil@example.com",
                "password1": "sufficiently-long-pw-1",
                "password2": "sufficiently-long-pw-1",
            },
        )
        assert not User.objects.filter(username="noaffil").exists()

    def test_affiliation_saved_to_profile(self, client):
        """Affiliation lands on TOM's Profile, so it survives approval.

        Stored there rather than on the registration request, which becomes
        historical once decided.
        """
        client.post(
            reverse("register"),
            {
                "username": "affiliated",
                "email": "affiliated@example.com",
                "password1": "sufficiently-long-pw-1",
                "password2": "sufficiently-long-pw-1",
                "affiliation": "Gemini Observatory",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        user = User.objects.get(username="affiliated")
        assert user.profile.affiliation == "Gemini Observatory"

    def test_inactive_user_cannot_log_in(self, client):
        """The account is inert until approved."""
        user = User.objects.create_user("pending", password="pw-long-enough-1")
        user.is_active = False
        user.save()
        assert not client.login(username="pending", password="pw-long-enough-1")

    def test_duplicate_email_rejected(self, client):
        """Two accounts cannot share an email address."""
        User.objects.create_user("first", email="dup@example.com")
        client.post(
            reverse("register"),
            {
                "username": "second",
                "email": "dup@example.com",
                "password1": "sufficiently-long-pw-1",
                "password2": "sufficiently-long-pw-1",
                "affiliation": "Somewhere",
            },
        )
        assert not User.objects.filter(username="second").exists()

    def test_registration_form_has_no_groups_field(self, client):
        """An unapproved stranger must not assign their own groups."""
        response = client.get(reverse("register"))
        assert b'name="groups"' not in response.content

    def test_queue_requires_superuser(self, client):
        """Only admins see the approval queue."""
        User.objects.create_user("plain", password="pw-long-enough-1")
        client.login(username="plain", password="pw-long-enough-1")
        response = client.get(reverse("registration-requests"))
        assert response.status_code in (302, 403)

    def test_approval_activates_account(self, client):
        """Approving lets the person sign in."""
        admin = User.objects.create_superuser(
            "admin", "admin@example.com", "pw-long-enough-1"
        )
        user = User.objects.create_user("waiting", password="pw-long-enough-1")
        user.is_active = False
        user.save()
        request = RegistrationRequest.objects.create(user=user)

        client.force_login(admin)
        client.post(
            reverse("decide-registration-request", args=[request.pk]),
            {"action": "approve"},
        )

        user.refresh_from_db()
        request.refresh_from_db()
        assert user.is_active
        assert request.status == RegistrationRequest.STATUS_APPROVED
        assert request.decided_by == admin

    def test_rejection_leaves_account_inactive(self, client):
        """Rejecting keeps the record and the account disabled."""
        admin = User.objects.create_superuser(
            "admin2", "admin2@example.com", "pw-long-enough-1"
        )
        user = User.objects.create_user("unwanted", password="pw-long-enough-1")
        user.is_active = False
        user.save()
        request = RegistrationRequest.objects.create(user=user)

        client.force_login(admin)
        client.post(
            reverse("decide-registration-request", args=[request.pk]),
            {"action": "reject"},
        )

        user.refresh_from_db()
        request.refresh_from_db()
        assert not user.is_active
        assert request.status == RegistrationRequest.STATUS_REJECTED
        # Kept, so the username cannot be immediately re-registered and the
        # decision is not lost.
        assert User.objects.filter(username="unwanted").exists()

    def test_cannot_decide_twice(self, client):
        """A decided request is not re-decidable."""
        admin = User.objects.create_superuser(
            "admin3", "admin3@example.com", "pw-long-enough-1"
        )
        user = User.objects.create_user("once", password="pw-long-enough-1")
        request = RegistrationRequest.objects.create(
            user=user, status=RegistrationRequest.STATUS_APPROVED
        )
        client.force_login(admin)
        response = client.post(
            reverse("decide-registration-request", args=[request.pk]),
            {"action": "reject"},
        )
        request.refresh_from_db()
        assert request.status == RegistrationRequest.STATUS_APPROVED
        assert response.status_code == 302


@pytest.mark.django_db()
class TestRegistrationDiscoverability:
    """The sign-up page has to be reachable without an account."""

    def test_login_page_links_to_register(self, client):
        """Someone with no account lands on login and needs a way onward.

        GOATS overrides tom_common's login template to add this link; the
        override only works because goats_tom precedes tom_common in
        INSTALLED_APPS, so this also guards that ordering.
        """
        response = client.get(reverse("login"))
        assert response.status_code == 200
        assert reverse("register").encode() in response.content

    def test_navbar_signals_registration_to_anonymous_visitors(self, client):
        """An anonymous visitor can see that signing up is possible.

        GOATS runs AUTH_STRATEGY = "READ_ONLY", so people can browse without
        being redirected to the login page. The navbar entry is labelled for
        both actions and leads to the login page, which carries the sign-up
        link.
        """
        response = client.get(reverse("home"))
        assert b"Login / Register" in response.content

    def test_navbar_hides_it_when_signed_in(self, client):
        """No point offering sign-in to somebody already signed in."""
        user = User.objects.create_user("signedin", password="pw-long-enough-1")
        client.force_login(user)
        response = client.get(reverse("home"))
        assert b"Login / Register" not in response.content

    def test_register_page_is_public(self, client):
        """The sign-up page must not require a login."""
        response = client.get(reverse("register"))
        assert response.status_code == 200

    def test_signed_in_user_redirected_away(self, client):
        """Registering while logged in is always a mistake."""
        user = User.objects.create_user("already", password="pw-long-enough-1")
        client.force_login(user)
        response = client.get(reverse("register"))
        assert response.status_code == 302


@pytest.mark.django_db()
class TestApprovalQueueDiscoverability:
    """The queue has to be findable, and only by admins."""

    def test_admin_sees_the_link(self, client):
        """An admin finds it in the user menu, with the other admin tools."""
        admin = User.objects.create_superuser(
            "queueadmin", "queueadmin@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        response = client.get(reverse("home"))
        assert reverse("registration-requests").encode() in response.content

    def test_non_admin_does_not(self, client):
        """Ordinary users are not shown an admin page they cannot open."""
        user = User.objects.create_user("plainuser", password="pw-long-enough-1")
        client.force_login(user)
        response = client.get(reverse("home"))
        assert reverse("registration-requests").encode() not in response.content


@pytest.mark.django_db()
class TestPendingAccountVisibility:
    """An unapproved account must be visibly unapproved."""

    def _register(self, client, username):
        client.post(
            reverse("register"),
            {
                "username": username,
                "email": f"{username}@example.com",
                "password1": "sufficiently-long-pw-1",
                "password2": "sufficiently-long-pw-1",
                "affiliation": "Somewhere",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        return User.objects.get(username=username)

    def test_registered_account_is_inactive(self, client):
        """Registration really does leave the account disabled."""
        user = self._register(client, "pendinguser")
        assert not user.is_active

    def test_user_list_marks_it_pending(self, client):
        """The list distinguishes it from an approved account.

        Self-registration creates the user immediately, so it appears in the
        list straight away -- without a status column it looks identical to
        an active account.
        """
        self._register(client, "pendinguser2")
        admin = User.objects.create_superuser(
            "listadmin", "listadmin@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        response = client.get(reverse("user-list"))
        assert b"Pending approval" in response.content

    def test_navbar_badge_counts_pending(self, client):
        """Admins see the count without relying on a live notification.

        The notification at registration only reaches connected sessions, so
        an administrator signed out at the time would otherwise see nothing.
        """
        self._register(client, "pendinguser3")
        admin = User.objects.create_superuser(
            "badgeadmin", "badgeadmin@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        response = client.get(reverse("home"))
        assert b"Account Requests" in response.content

    def test_badge_absent_with_no_pending(self, client):
        """No badge when the queue is empty."""
        from goats_tom.templatetags.registration_extras import (
            pending_registration_count,
        )

        assert pending_registration_count() == 0

    def test_active_account_shows_active(self, client):
        """An approved account reads as Active."""
        admin = User.objects.create_superuser(
            "activeadmin", "activeadmin@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        response = client.get(reverse("user-list"))
        assert b"Active" in response.content


@pytest.mark.django_db()
class TestUserListTableIntegrity:
    """The user table's rows must line up with its headers.

    Regression test: adding the Status column accidentally deleted the email
    cell, so every column after it shifted one to the left -- the Active badge
    appeared under "Email" and the email address vanished. Nothing caught it,
    because every individual value was still present *somewhere* on the page.
    """

    def _table(self, client):
        """Return (headers, cells) for the admin's own row.

        Scoped to the single ``<table>`` containing that row: the page renders
        more than one table, so counting every ``<th>`` on it would compare a
        row against the wrong header set.
        """
        import re

        admin = User.objects.create_superuser(
            "tableadmin", "tableadmin@example.com", "pw-long-enough-1"
        )
        admin.first_name, admin.last_name = "Table", "Admin"
        admin.save()
        client.force_login(admin)
        html = client.get(reverse("user-list")).content.decode()

        table = next(
            (
                t
                for t in re.findall(r"<table.*?</table>", html, re.S)
                if "tableadmin" in t
            ),
            None,
        )
        assert table, "table containing the admin row not found"

        headers = re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)
        row = re.search(r"<tr>\s*<td[^>]*>\s*tableadmin.*?</tr>", table, re.S)
        assert row, "admin row not found"
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(0), re.S)
        return headers, cells

    def test_row_has_one_cell_per_header(self, client):
        """A dropped or extra cell shifts every later column."""
        headers, cells = self._table(client)
        assert len(cells) == len(headers), (
            f"{len(cells)} cells against {len(headers)} headers"
        )

    def test_email_is_in_the_email_column(self, client):
        """The address must sit under Email, not somewhere adjacent."""
        headers, cells = self._table(client)
        stripped = [" ".join(h.split()) for h in headers]
        email_index = next(
            i for i, h in enumerate(stripped) if h.startswith("Email")
        )
        assert "tableadmin@example.com" in cells[email_index]

    def test_status_is_in_the_status_column(self, client):
        """And the badge under Status."""
        headers, cells = self._table(client)
        stripped = [" ".join(h.split()) for h in headers]
        status_index = next(
            i for i, h in enumerate(stripped) if h.startswith("Status")
        )
        assert "Active" in cells[status_index]


@pytest.mark.django_db()
class TestRequestedGroups:
    """Applicants ask for groups; administrators decide."""

    def _register(self, client, username, groups=()):
        data = {
            "username": username,
            "email": f"{username}@example.com",
            "password1": "sufficiently-long-pw-1",
            "password2": "sufficiently-long-pw-1",
            "affiliation": "Somewhere",
            # Required since first/last name became mandatory on the public
            # form -- an administrator judging a stranger needs a real name.
            "first_name": "Test",
            "last_name": "User",
        }
        if groups:
            data["requested_groups"] = [g.pk for g in groups]
        client.post(reverse("register"), data)
        return User.objects.get(username=username)

    def test_groups_offered_on_the_form(self, client):
        """The applicant can see and choose groups."""
        Group.objects.create(name="my-collaboration")
        response = client.get(reverse("register"))
        assert b'name="requested_groups"' in response.content
        assert b"my-collaboration" in response.content

    def test_automatic_groups_not_offered(self, client):
        """Personal and PI groups stay hidden, as elsewhere."""
        pi = User.objects.create_user("somepi")
        AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-somepi"), pi=pi
        )
        response = client.get(reverse("register"))
        assert b"antares-somepi" not in response.content

    def test_selection_is_recorded_not_applied(self, client):
        """Choosing a group must not grant it.

        Registration is public, so an applied selection would let anyone give
        themselves access to whatever that group shares.
        """
        group = Group.objects.create(name="wanted-team")
        user = self._register(client, "hopeful", groups=[group])
        assert not user.groups.filter(pk=group.pk).exists()
        assert group in user.registration_request.requested_groups.all()

    def test_approval_grants_ticked_groups(self, client):
        """What the admin submits is what gets granted."""
        group = Group.objects.create(name="granted-team")
        user = self._register(client, "hopeful2", groups=[group])
        admin = User.objects.create_superuser(
            "gadmin", "gadmin@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        client.post(
            reverse("decide-registration-request", args=[user.registration_request.pk]),
            {"action": "approve", "grant_groups": [group.pk]},
        )
        assert user.groups.filter(pk=group.pk).exists()

    def test_admin_can_grant_less_than_requested(self, client):
        """Unticking a requested group withholds it."""
        group = Group.objects.create(name="denied-team")
        user = self._register(client, "hopeful3", groups=[group])
        admin = User.objects.create_superuser(
            "gadmin2", "gadmin2@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        client.post(
            reverse("decide-registration-request", args=[user.registration_request.pk]),
            {"action": "approve"},
        )
        user.refresh_from_db()
        assert user.is_active
        assert not user.groups.filter(pk=group.pk).exists()

    def test_posted_automatic_group_is_ignored(self, client):
        """A crafted post cannot slip somebody into a managed group.

        ANTARES PI group membership is supposed to arrive with dashboard
        permissions attached, via the join-request flow.
        """
        pi = User.objects.create_user("pi_for_test")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-pi_for_test"), pi=pi
        )
        user = self._register(client, "sneaky")
        admin = User.objects.create_superuser(
            "gadmin3", "gadmin3@example.com", "pw-long-enough-1"
        )
        client.force_login(admin)
        client.post(
            reverse("decide-registration-request", args=[user.registration_request.pk]),
            {"action": "approve", "grant_groups": [pi_group.group.pk]},
        )
        assert not user.groups.filter(pk=pi_group.group.pk).exists()
