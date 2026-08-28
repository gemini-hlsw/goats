
import pytest
from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.urls import reverse

from goats_tom.antares_access import (
    accessible_subscriptions,
    can_configure,
    can_save_targets,
    can_view_dashboard,
    get_subscription_for_view,
    membership_for,
)
from goats_tom.models import (
    AntaresDashboardMembership,
    AntaresGroupJoinRequest,
    AntaresKafkaLogin,
    AntaresLocus,
    AntaresPIGroup,
    AntaresStreamSubscription,
)


@pytest.fixture()
def pi(db):
    """A PI who owns a subscription and a group."""
    return User.objects.create_user("pi_alice")


@pytest.fixture()
def other_pi(db):
    """A second, unrelated PI -- used to prove dashboards are isolated."""
    return User.objects.create_user("pi_bob")


@pytest.fixture()
def member(db):
    """A user who will be granted access to `pi`'s dashboard."""
    return User.objects.create_user("student")


@pytest.fixture()
def stranger(db):
    """A user with no relationship to any dashboard."""
    return User.objects.create_user("stranger")


@pytest.fixture()
def admin(db):
    """A superuser."""
    return User.objects.create_superuser("admin", "admin@example.com", "pw")


@pytest.fixture()
def subscription(pi):
    """`pi`'s subscription."""
    return AntaresStreamSubscription.objects.create(owner=pi, topics=["topic_a"])


@pytest.fixture()
def other_subscription(other_pi):
    """`other_pi`'s subscription."""
    return AntaresStreamSubscription.objects.create(
        owner=other_pi, topics=["topic_b"]
    )


@pytest.fixture()
def pi_group(pi):
    """`pi`'s group."""
    group = Group.objects.create(name="antares-pi_alice")
    return AntaresPIGroup.objects.create(group=group, pi=pi)


@pytest.mark.django_db()
class TestConsumerGroupNaming:
    """Tests for `AntaresStreamSubscription.resolved_consumer_group`.

    Two subscriptions sharing a Kafka consumer group name is a silent
    data-loss bug -- Kafka balances partitions between same-named consumers,
    so each would receive only a subset of alerts with no error anywhere.
    These tests pin the property that prevents it.
    """

    def test_derived_from_primary_key(self, subscription):
        """A blank consumer_group still yields a per-subscription name."""
        assert subscription.resolved_consumer_group == (
            f"goats-antares-{subscription.pk}"
        )

    def test_user_input_is_only_a_suffix(self, subscription):
        """User input is appended, never used as the whole name."""
        subscription.consumer_group = "replay2"
        subscription.save()
        assert subscription.resolved_consumer_group == (
            f"goats-antares-{subscription.pk}-replay2"
        )

    def test_distinct_across_subscriptions(
        self, subscription, other_subscription
    ):
        """Two subscriptions never resolve to the same group name."""
        assert (
            subscription.resolved_consumer_group
            != other_subscription.resolved_consumer_group
        )

    def test_identical_user_input_still_distinct(
        self, subscription, other_subscription
    ):
        """Two users entering the same suffix still get distinct names."""
        subscription.consumer_group = "replay"
        subscription.save()
        other_subscription.consumer_group = "replay"
        other_subscription.save()
        assert (
            subscription.resolved_consumer_group
            != other_subscription.resolved_consumer_group
        )

    def test_whitespace_only_suffix_ignored(self, subscription):
        """A whitespace-only suffix doesn't produce a trailing dash."""
        subscription.consumer_group = "   "
        subscription.save()
        assert subscription.resolved_consumer_group == (
            f"goats-antares-{subscription.pk}"
        )


@pytest.mark.django_db()
class TestPIGroupAutoCreation:
    """Tests for the `AntaresKafkaLogin` post-save signal."""

    def test_group_created_on_credential_save(self, pi):
        """Storing credentials gives the user a PI group."""
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pi_group = AntaresPIGroup.objects.filter(pi=pi).first()
        assert pi_group is not None
        assert pi_group.group.name == "antares-pi_alice"

    def test_pi_joins_own_group(self, pi):
        """The PI is added to their own group, for target sharing."""
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pi_group = AntaresPIGroup.objects.get(pi=pi)
        assert pi.groups.filter(pk=pi_group.group.pk).exists()

    def test_idempotent_on_resave(self, pi):
        """Updating credentials doesn't create a second group."""
        login = AntaresKafkaLogin.objects.create(
            user=pi, api_key="k", api_secret="s"
        )
        login.api_key = "k2"
        login.save()
        assert AntaresPIGroup.objects.filter(pi=pi).count() == 1

    def test_name_collision_is_suffixed(self, pi):
        """An existing group of the same name doesn't break creation."""
        Group.objects.create(name="antares-pi_alice")
        AntaresKafkaLogin.objects.create(user=pi, api_key="k", api_secret="s")
        pi_group = AntaresPIGroup.objects.get(pi=pi)
        assert pi_group.group.name == "antares-pi_alice-2"


@pytest.mark.django_db()
class TestDashboardAccess:
    """Tests for `goats_tom.antares_access`."""

    def test_owner_has_full_access(self, pi, subscription):
        """The PI may view, save, and configure their own dashboard."""
        assert can_view_dashboard(pi, subscription)
        assert can_save_targets(pi, subscription)
        assert can_configure(pi, subscription)

    def test_stranger_has_no_access(self, stranger, subscription):
        """A user with no membership has no access at all."""
        assert not can_view_dashboard(stranger, subscription)
        assert not can_save_targets(stranger, subscription)
        assert not can_configure(stranger, subscription)

    def test_other_pi_cannot_see_dashboard(
        self, other_pi, subscription
    ):
        """Owning one dashboard grants nothing on another."""
        assert not can_view_dashboard(other_pi, subscription)

    def test_view_only_member(self, member, pi, pi_group, subscription):
        """A view-only member can view but not save or configure."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group,
            user=member,
            can_view_dashboard=True,
            can_save_targets=False,
            granted_by=pi,
        )
        assert can_view_dashboard(member, subscription)
        assert not can_save_targets(member, subscription)
        assert not can_configure(member, subscription)

    def test_member_granted_save(self, member, pi, pi_group, subscription):
        """Granting save permission allows saving."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group,
            user=member,
            can_view_dashboard=True,
            can_save_targets=True,
            granted_by=pi,
        )
        assert can_save_targets(member, subscription)

    def test_save_requires_view(self, member, pi, pi_group, subscription):
        """Revoking view access also stops saving.

        Otherwise a member could keep saving from a dashboard they can no
        longer see.
        """
        membership = AntaresDashboardMembership.objects.create(
            pi_group=pi_group,
            user=member,
            can_view_dashboard=False,
            can_save_targets=True,
            granted_by=pi,
        )
        assert membership.can_save_targets
        assert not can_save_targets(member, subscription)

    def test_membership_does_not_leak_across_groups(
        self, member, pi, pi_group, other_subscription
    ):
        """Membership in one PI's group grants nothing on another's."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        assert not can_view_dashboard(member, other_subscription)

    def test_superuser_may_view_but_not_save_or_configure(
        self, admin, subscription
    ):
        """Superusers can view any dashboard but must not act on it.

        Saving attributes the target to the acting user and grants them
        access, so an admin saving on a PI's behalf would misattribute it.
        """
        assert can_view_dashboard(admin, subscription)
        assert not can_save_targets(admin, subscription)
        assert not can_configure(admin, subscription)

    def test_membership_for_returns_none_for_owner(self, pi, subscription):
        """Owners are not members of their own group."""
        assert membership_for(pi, subscription) is None

    def test_none_subscription_denies_everything(self, pi):
        """A missing subscription is never accessible."""
        assert not can_view_dashboard(pi, None)
        assert not can_save_targets(pi, None)
        assert not can_configure(pi, None)


@pytest.mark.django_db()
class TestSubscriptionResolution:
    """Tests for `accessible_subscriptions` and `get_subscription_for_view`."""

    def test_own_subscription_wins(
        self, pi, pi_group, subscription, other_subscription
    ):
        """A PI who is also a member lands on their own dashboard."""
        other_group = AntaresPIGroup.objects.get_or_create(
            group=Group.objects.create(name="antares-pi_bob"),
            pi=other_subscription.owner,
        )[0]
        AntaresDashboardMembership.objects.create(
            pi_group=other_group, user=pi, can_view_dashboard=True
        )
        assert get_subscription_for_view(pi).pk == subscription.pk

    def test_member_resolves_to_shared_dashboard(
        self, member, pi_group, subscription
    ):
        """A member with no dashboard of their own sees the shared one."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        assert get_subscription_for_view(member).pk == subscription.pk

    def test_requesting_inaccessible_dashboard_returns_none(
        self, member, pi_group, subscription, other_subscription
    ):
        """Asking for a forbidden dashboard yields nothing, not a fallback.

        Silently substituting an accessible dashboard would render data
        under the wrong heading.
        """
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        assert (
            get_subscription_for_view(member, other_subscription.pk) is None
        )

    def test_stranger_resolves_to_none(self, stranger, subscription):
        """A user with no access resolves to no dashboard."""
        assert get_subscription_for_view(stranger) is None

    def test_accessible_excludes_unshared(
        self, member, pi_group, subscription, other_subscription
    ):
        """Only dashboards the user owns or is a member of are listed."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        assert list(
            accessible_subscriptions(member).values_list("pk", flat=True)
        ) == [subscription.pk]

    def test_accessible_empty_for_stranger(self, stranger, subscription):
        """A stranger sees nothing."""
        assert not accessible_subscriptions(stranger).exists()

    def test_view_permission_required_to_be_listed(
        self, member, pi_group, subscription
    ):
        """A membership without view permission doesn't grant a listing."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=False
        )
        assert not accessible_subscriptions(member).exists()


@pytest.mark.django_db()
class TestLocusIsolation:
    """Tests for per-subscription locus scoping."""

    def test_same_locus_in_two_subscriptions(
        self, subscription, other_subscription
    ):
        """The same locus may exist once per subscription.

        Each subscription applies its own `handler_code`, so one locus can
        legitimately be kept by one and rejected by another.
        """
        for sub in (subscription, other_subscription):
            AntaresLocus.objects.create(
                subscription=sub,
                locus_id="ANT2026abc",
                ra=1.0,
                dec=2.0,
                latest_alert_id="alert",
            )
        assert AntaresLocus.objects.filter(locus_id="ANT2026abc").count() == 2

    def test_duplicate_within_subscription_rejected(self, subscription):
        """A locus can't be duplicated within one subscription."""
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT2026abc",
            ra=1.0,
            dec=2.0,
            latest_alert_id="alert",
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            AntaresLocus.objects.create(
                subscription=subscription,
                locus_id="ANT2026abc",
                ra=1.0,
                dec=2.0,
                latest_alert_id="alert2",
            )

    def test_deleting_subscription_clears_its_loci(self, subscription):
        """Loci are removed with their subscription, not orphaned."""
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT2026abc",
            ra=1.0,
            dec=2.0,
            latest_alert_id="alert",
        )
        subscription.delete()
        assert not AntaresLocus.objects.exists()


@pytest.mark.django_db()
class TestJoinRequests:
    """Tests for `AntaresGroupJoinRequest` constraints."""

    def test_single_pending_request_per_group(self, stranger, pi_group):
        """A user can't queue two pending requests for the same group."""
        AntaresGroupJoinRequest.objects.create(
            requester=stranger, pi_group=pi_group
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            AntaresGroupJoinRequest.objects.create(
                requester=stranger, pi_group=pi_group
            )

    def test_can_reapply_after_denial(self, stranger, pi_group):
        """A denied user may request again.

        The constraint is on *pending* requests only, so denials don't
        permanently bar someone, and the decision history is kept.
        """
        request = AntaresGroupJoinRequest.objects.create(
            requester=stranger, pi_group=pi_group
        )
        request.status = AntaresGroupJoinRequest.STATUS_DENIED
        request.save()
        AntaresGroupJoinRequest.objects.create(
            requester=stranger, pi_group=pi_group
        )
        assert (
            AntaresGroupJoinRequest.objects.filter(requester=stranger).count()
            == 2
        )

    def test_defaults_to_pending_view_only(self, stranger, pi_group):
        """A new request asks to view by default, not to save."""
        request = AntaresGroupJoinRequest.objects.create(
            requester=stranger, pi_group=pi_group
        )
        assert request.status == AntaresGroupJoinRequest.STATUS_PENDING
        assert request.requested_view_dashboard
        assert not request.requested_save_targets


@pytest.mark.django_db()
class TestMembershipConstraints:
    """Tests for `AntaresDashboardMembership` constraints."""

    def test_one_membership_per_group_and_user(self, member, pi_group):
        """A user can't hold two memberships in the same group."""
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            AntaresDashboardMembership.objects.create(
                pi_group=pi_group, user=member
            )

    def test_save_defaults_off(self, member, pi_group):
        """Saving targets is opt-in, not implied by viewing."""
        membership = AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member
        )
        assert membership.can_view_dashboard
        assert not membership.can_save_targets


@pytest.mark.django_db()
class TestMembershipService:
    """Tests for `goats_tom.antares_membership` state transitions."""

    def test_requestable_excludes_own_group(self, pi, pi_group):
        """A PI is never offered their own group."""
        from goats_tom.antares_membership import requestable_pi_groups

        assert not requestable_pi_groups(pi).exists()

    def test_requestable_includes_other_group(self, stranger, pi_group):
        """An unrelated user may request the group."""
        from goats_tom.antares_membership import requestable_pi_groups

        assert list(requestable_pi_groups(stranger)) == [pi_group]

    def test_requestable_excludes_pending(self, stranger, pi_group):
        """A group with a pending request isn't offered again."""
        from goats_tom.antares_membership import (
            create_join_request,
            requestable_pi_groups,
        )

        create_join_request(stranger, pi_group)
        assert not requestable_pi_groups(stranger).exists()

    def test_requestable_excludes_existing_member(self, member, pi_group):
        """An existing member isn't offered the group."""
        from goats_tom.antares_membership import requestable_pi_groups

        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member
        )
        assert not requestable_pi_groups(member).exists()

    def test_cannot_request_own_group(self, pi, pi_group):
        """Requesting your own group is an error, not a no-op."""
        from goats_tom.antares_membership import (
            JoinRequestError,
            create_join_request,
        )

        with pytest.raises(JoinRequestError):
            create_join_request(pi, pi_group)

    def test_cannot_request_twice(self, stranger, pi_group):
        """A second pending request raises rather than 500-ing."""
        from goats_tom.antares_membership import (
            JoinRequestError,
            create_join_request,
        )

        create_join_request(stranger, pi_group)
        with pytest.raises(JoinRequestError), transaction.atomic():
            create_join_request(stranger, pi_group)

    def test_approve_creates_membership_and_group(
        self, pi, stranger, pi_group, subscription
    ):
        """Approving grants dashboard access and joins the auth group."""
        from goats_tom.antares_membership import (
            approve_join_request,
            create_join_request,
        )

        join_request = create_join_request(stranger, pi_group)
        approve_join_request(
            join_request, decided_by=pi, grant_view=True, grant_save=True
        )

        join_request.refresh_from_db()
        assert join_request.status == AntaresGroupJoinRequest.STATUS_APPROVED
        assert join_request.decided_by == pi
        assert join_request.decided_at is not None
        assert can_view_dashboard(stranger, subscription)
        assert can_save_targets(stranger, subscription)
        assert stranger.groups.filter(pk=pi_group.group.pk).exists()

    def test_approve_can_narrow_permissions(
        self, pi, stranger, pi_group, subscription
    ):
        """A PI may grant less than was requested."""
        from goats_tom.antares_membership import (
            approve_join_request,
            create_join_request,
        )

        join_request = create_join_request(
            stranger, pi_group, request_save_targets=True
        )
        approve_join_request(
            join_request, decided_by=pi, grant_view=True, grant_save=False
        )
        assert can_view_dashboard(stranger, subscription)
        assert not can_save_targets(stranger, subscription)

    def test_cannot_approve_twice(self, pi, stranger, pi_group):
        """A decided request can't be decided again."""
        from goats_tom.antares_membership import (
            JoinRequestError,
            approve_join_request,
            create_join_request,
        )

        join_request = create_join_request(stranger, pi_group)
        approve_join_request(join_request, decided_by=pi)
        with pytest.raises(JoinRequestError):
            approve_join_request(join_request, decided_by=pi)

    def test_deny_grants_nothing(self, pi, stranger, pi_group, subscription):
        """Denying leaves the user without access."""
        from goats_tom.antares_membership import (
            create_join_request,
            deny_join_request,
        )

        join_request = create_join_request(stranger, pi_group)
        deny_join_request(join_request, decided_by=pi)

        join_request.refresh_from_db()
        assert join_request.status == AntaresGroupJoinRequest.STATUS_DENIED
        assert not can_view_dashboard(stranger, subscription)
        assert not AntaresDashboardMembership.objects.filter(
            user=stranger
        ).exists()

    def test_revoke_removes_access_and_group(
        self, pi, stranger, pi_group, subscription
    ):
        """Revoking removes both the membership and the auth group."""
        from goats_tom.antares_membership import (
            approve_join_request,
            create_join_request,
            revoke_membership,
        )

        join_request = create_join_request(stranger, pi_group)
        membership = approve_join_request(join_request, decided_by=pi)
        revoke_membership(membership)

        assert not can_view_dashboard(stranger, subscription)
        assert not stranger.groups.filter(pk=pi_group.group.pk).exists()

    def test_can_rerequest_after_denial(self, pi, stranger, pi_group):
        """A denied user may ask again."""
        from goats_tom.antares_membership import (
            create_join_request,
            deny_join_request,
            requestable_pi_groups,
        )

        join_request = create_join_request(stranger, pi_group)
        deny_join_request(join_request, decided_by=pi)
        assert requestable_pi_groups(stranger).exists()
        create_join_request(stranger, pi_group)


@pytest.mark.django_db()
class TestRequestAccessEmptyStates:
    """The empty state must say which empty state it is."""

    def test_message_when_no_pi_groups_exist(self, client, stranger):
        """Nothing to request yet."""
        client.force_login(stranger)
        response = client.get(reverse("antares-request-access"))
        assert b"no dashboards to request yet" in response.content

    def test_message_after_requesting_everything(
        self, client, stranger, pi_group
    ):
        """Having asked for it all is not the same as nothing existing.

        Regression test: one message covered both, so immediately after a
        successful request the page said access was requested and then
        implied there had been nothing to request.
        """
        from goats_tom.antares_membership import create_join_request

        create_join_request(stranger, pi_group)
        client.force_login(stranger)
        response = client.get(reverse("antares-request-access"))
        # No banner for this case any more -- the "Your requests" table below
        # already says it, with more detail. The "nothing exists" message must
        # still not appear, since something does exist.
        assert b"no dashboards to request yet" not in response.content
        assert b"Your requests" in response.content
