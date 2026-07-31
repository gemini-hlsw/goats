"""Tests for read-only ingestion visibility and the dashboard switcher."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.models import (
    AntaresDashboardMembership,
    AntaresPIGroup,
    AntaresStreamSubscription,
)


@pytest.fixture()
def pi(db):
    """A PI who owns a subscription and a group."""
    return User.objects.create_user("thepi", password="pw-long-enough-1")


@pytest.fixture()
def pi_group(pi):
    """The PI's group."""
    return AntaresPIGroup.objects.create(
        group=Group.objects.create(name="antares-thepi"), pi=pi
    )


@pytest.fixture()
def subscription(pi):
    """The PI's subscription, with a handler set."""
    return AntaresStreamSubscription.objects.create(
        owner=pi,
        topics=["pi_only_topic_zzz"],
        handler_code="def myfilter(locus):\n    return True\n",
    )


@pytest.fixture()
def member(db, pi_group):
    """A user with view access to the PI's dashboard."""
    user = User.objects.create_user("student", password="pw-long-enough-1")
    AntaresDashboardMembership.objects.create(
        pi_group=pi_group, user=user, can_view_dashboard=True
    )
    return user


@pytest.mark.django_db()
class TestReadOnlyIngestionPage:
    """A member sees the configuration but cannot change it."""

    def test_member_sees_configuration(self, client, member, subscription):
        """Topics and handler code are visible to a member."""
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"))
        assert response.status_code == 200
        assert b"pi_only_topic_zzz" in response.content
        assert b"myfilter" in response.content

    def test_member_gets_no_form(self, client, member, subscription):
        """No submittable form is rendered for a member.

        A disabled form would still post if the attribute were stripped
        client-side, so nothing submittable is rendered at all.
        """
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b'name="topics"' not in response.content
        assert b"Request access" not in response.content

    def test_member_page_names_the_owner(self, client, member, subscription):
        """The page says whose configuration is being shown."""
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"thepi" in response.content

    def test_owner_still_gets_the_form(self, client, pi, subscription):
        """The PI's own page is unchanged."""
        client.force_login(pi)
        response = client.get(reverse("antares-stream-subscribe"))
        assert response.status_code == 200
        assert b'name="topics"' in response.content

    def test_member_cannot_start_a_consumer(self, client, member, subscription):
        """Posting must not create a subscription owned by the member.

        Regression test: the page used to render a blank form for members, and
        submitting it quietly made them a PI with a consumer that could never
        start for lack of their own credentials.
        """
        client.force_login(member)
        client.post(
            reverse("antares-stream-subscribe"),
            {"topics": "pi_only_topic_zzz", "consumer_group": ""},
        )
        assert not AntaresStreamSubscription.objects.filter(owner=member).exists()

    def test_stranger_sees_their_own_blank_form(self, client, subscription):
        """Somebody with no access is unaffected by the read-only path."""
        stranger = User.objects.create_user("nobody", password="pw-long-enough-1")
        client.force_login(stranger)
        response = client.get(reverse("antares-stream-subscribe"))
        assert response.status_code == 200
        assert b"pi_only_topic_zzz" not in response.content


@pytest.mark.django_db()
class TestDashboardControls:
    """Controls are gated on ownership."""

    def test_member_has_no_clear_button(self, client, member, subscription):
        """Clearing destroys the whole team's view; owner only."""
        client.force_login(member)
        response = client.get(reverse("antares-locus-dashboard"))
        assert b"Clear dashboard" not in response.content

    def test_owner_has_clear_button(self, client, pi, subscription):
        """The PI keeps the control."""
        client.force_login(pi)
        response = client.get(reverse("antares-locus-dashboard"))
        assert b"Clear dashboard" in response.content

    def test_member_offered_read_only_link(self, client, member, subscription):
        """Members get "View ingestion configuration", not "Manage"."""
        client.force_login(member)
        response = client.get(reverse("antares-locus-dashboard"))
        assert b"View ingestion configuration" in response.content

    def test_member_clear_post_is_rejected(self, client, member, subscription):
        """The gate is enforced server-side, not only in the template."""
        from goats_tom.models import AntaresLocus

        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT1",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a",
        )
        client.force_login(member)
        client.post(reverse("antares-locus-clear"))
        assert AntaresLocus.objects.filter(subscription=subscription).exists()


@pytest.mark.django_db()
class TestDashboardSwitcher:
    """A user in several PI groups can choose which dashboard to view."""

    @pytest.fixture()
    def second_dashboard(self, member):
        """A second PI whose dashboard `member` can also view."""
        other_pi = User.objects.create_user("otherpi")
        other_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-otherpi"), pi=other_pi
        )
        AntaresDashboardMembership.objects.create(
            pi_group=other_group, user=member, can_view_dashboard=True
        )
        return AntaresStreamSubscription.objects.create(
            owner=other_pi, topics=["second_topic_yyy"]
        )

    def test_switcher_hidden_with_one_dashboard(
        self, client, member, subscription
    ):
        """No switcher when there is no choice to make."""
        client.force_login(member)
        response = client.get(reverse("antares-locus-dashboard"))
        assert b'id="dashboard-select"' not in response.content

    def test_switcher_shown_with_two(
        self, client, member, subscription, second_dashboard
    ):
        """Both dashboards are offered."""
        client.force_login(member)
        response = client.get(reverse("antares-locus-dashboard"))
        assert b'id="dashboard-select"' in response.content
        assert b"thepi" in response.content
        assert b"otherpi" in response.content

    def test_switching_selects_the_requested_dashboard(
        self, client, member, subscription, second_dashboard
    ):
        """The chosen dashboard's topics are shown."""
        client.force_login(member)
        response = client.get(
            reverse("antares-locus-dashboard"),
            {"subscription": second_dashboard.pk},
        )
        assert b"second_topic_yyy" in response.content

    def test_cannot_switch_to_an_inaccessible_dashboard(
        self, client, member, subscription
    ):
        """Requesting a forbidden dashboard shows nothing, not a fallback."""
        outsider = User.objects.create_user("outsider")
        hidden = AntaresStreamSubscription.objects.create(
            owner=outsider, topics=["secret_topic"]
        )
        client.force_login(member)
        response = client.get(
            reverse("antares-locus-dashboard"), {"subscription": hidden.pk}
        )
        assert b"secret_topic" not in response.content


@pytest.mark.django_db()
class TestReadOnlyStatusBanner:
    """The status banner must not offer controls a member cannot use."""

    def test_member_sees_no_stop_button(self, client, member, subscription):
        """Stopping ingestion affects the whole team; owner only."""
        subscription.is_running = True
        subscription.save()
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"Stop ingestion" not in response.content

    def test_owner_sees_stop_button(self, client, pi, subscription):
        """The PI keeps the control."""
        subscription.is_running = True
        subscription.save()
        client.force_login(pi)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"Stop ingestion" in response.content

    def test_member_status_poll_still_shows_the_dashboard(
        self, client, member, subscription
    ):
        """The htmx poll must not blank the banner three seconds in.

        Regression test: the polling endpoint was scoped to the requesting
        user's own subscription, so a member got an empty response back and
        the status silently disappeared after first paint.
        """
        subscription.is_running = True
        subscription.save()
        client.force_login(member)
        response = client.get(
            reverse("antares-stream-status"), {"subscription": subscription.pk}
        )
        assert b"Currently subscribed to" in response.content
        assert b"Stop ingestion" not in response.content

    def test_member_stop_post_is_ignored(self, client, member, subscription):
        """Enforced server-side, not just hidden in the template."""
        subscription.is_running = True
        subscription.save()
        client.force_login(member)
        client.post(reverse("antares-stream-subscribe"), {"action": "stop"})
        subscription.refresh_from_db()
        assert subscription.is_running
