"""Tests for shared-target saving across teams."""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from guardian.shortcuts import get_perms
from tom_targets.models import Target

from goats_tom.antares_target_save import (
    save_locus_as_target,
    share_target_with_group,
)
from goats_tom.models import AntaresTargetSave

LOCUS = "ANT2026abc"


@pytest.fixture()
def team_a(db):
    """First team: a user and their group."""
    user = User.objects.create_user("alice")
    group = Group.objects.create(name="antares-alice")
    user.groups.add(group)
    return user, group


@pytest.fixture()
def team_b(db):
    """Second team, unrelated to the first."""
    user = User.objects.create_user("bob")
    group = Group.objects.create(name="antares-bob")
    user.groups.add(group)
    return user, group


@pytest.fixture()
def fake_alert(db):
    """Patch the ANTARES broker so no network call is made.

    `save_locus_as_target` fetches the locus, converts it to a target, and
    ingests its light curve. All of that is stubbed: these tests are about
    which permissions end up where, not about alert parsing. The light curve
    methods are left as no-op mocks rather than removed, since the real code
    calls them and swallows their failures -- stubbing keeps a real failure
    from being mistaken for success.
    """
    from unittest.mock import MagicMock

    broker = MagicMock()
    broker.fetch_alerts.return_value = iter([{"locus_id": LOCUS}])
    broker.to_target.return_value = (
        Target(name=LOCUS, type=Target.SIDEREAL, ra=10.0, dec=20.0),
        {},
        [],
    )

    with patch(
        "goats_tom.antares_target_save.tom_alerts_get_service_class",
        return_value=lambda: broker,
    ):
        yield broker


@pytest.mark.django_db()
class TestShareTargetWithGroup:
    """Tests for the group-permission helper."""

    def test_view_only_by_default(self, team_a):
        """A later team gets view, never change or delete."""
        _, group = team_a
        target = Target.objects.create(
            name="T1", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        share_target_with_group(target, group)
        perms = set(get_perms(group, target))
        assert "view_target" in perms
        assert "change_target" not in perms
        assert "delete_target" not in perms

    def test_full_access_when_requested(self, team_a):
        """The creating team gets change and delete too."""
        _, group = team_a
        target = Target.objects.create(
            name="T2", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        share_target_with_group(target, group, full_access=True)
        perms = set(get_perms(group, target))
        assert {"view_target", "change_target", "delete_target"} <= perms


@pytest.mark.django_db()
class TestSharedSaving:
    """Tests for one Target per locus, shared between teams."""

    def test_first_save_creates_target(self, team_a, fake_alert):
        """The first save creates the target and records the save."""
        user, group = team_a
        target = save_locus_as_target(
            LOCUS, saved_by=user, share_with_group=group
        )
        assert target.pk is not None
        assert AntaresTargetSave.objects.filter(
            locus_id=LOCUS, saved_by=user
        ).exists()

    def test_first_team_gets_full_access(self, team_a, fake_alert):
        """The creating team can change and delete."""
        user, group = team_a
        target = save_locus_as_target(
            LOCUS, saved_by=user, share_with_group=group
        )
        assert {"view_target", "change_target", "delete_target"} <= set(
            get_perms(group, target)
        )

    def test_second_save_does_not_duplicate(
        self, team_a, team_b, fake_alert
    ):
        """A second team saving the same locus reuses the one target."""
        user_a, group_a = team_a
        user_b, group_b = team_b

        first = save_locus_as_target(
            LOCUS, saved_by=user_a, share_with_group=group_a
        )
        second = save_locus_as_target(
            LOCUS, saved_by=user_b, share_with_group=group_b
        )

        assert first.pk == second.pk
        assert Target.objects.filter(name=LOCUS).count() == 1

    def test_second_team_gets_view_only(self, team_a, team_b, fake_alert):
        """The second team can look but not alter.

        Otherwise either team could delete a target the other is actively
        observing.
        """
        user_a, group_a = team_a
        user_b, group_b = team_b

        save_locus_as_target(LOCUS, saved_by=user_a, share_with_group=group_a)
        target = save_locus_as_target(
            LOCUS, saved_by=user_b, share_with_group=group_b
        )

        b_perms = set(get_perms(group_b, target))
        assert "view_target" in b_perms
        assert "change_target" not in b_perms
        assert "delete_target" not in b_perms

    def test_first_team_keeps_full_access_after_sharing(
        self, team_a, team_b, fake_alert
    ):
        """Sharing doesn't downgrade the original team."""
        user_a, group_a = team_a
        user_b, group_b = team_b

        save_locus_as_target(LOCUS, saved_by=user_a, share_with_group=group_a)
        target = save_locus_as_target(
            LOCUS, saved_by=user_b, share_with_group=group_b
        )

        assert {"view_target", "change_target", "delete_target"} <= set(
            get_perms(group_a, target)
        )

    def test_both_saves_recorded(self, team_a, team_b, fake_alert):
        """Each team's save is attributed separately."""
        user_a, group_a = team_a
        user_b, group_b = team_b

        save_locus_as_target(LOCUS, saved_by=user_a, share_with_group=group_a)
        save_locus_as_target(LOCUS, saved_by=user_b, share_with_group=group_b)

        assert AntaresTargetSave.objects.filter(locus_id=LOCUS).count() == 2

    def test_resaving_is_idempotent(self, team_a, fake_alert):
        """The same user saving twice doesn't accumulate rows."""
        user, group = team_a
        save_locus_as_target(LOCUS, saved_by=user, share_with_group=group)
        save_locus_as_target(LOCUS, saved_by=user, share_with_group=group)
        assert (
            AntaresTargetSave.objects.filter(
                locus_id=LOCUS, saved_by=user
            ).count()
            == 1
        )

    def test_second_save_does_not_refetch(self, team_a, team_b, fake_alert):
        """Sharing an existing target makes no broker call.

        The data is already attached to the target and shared with it, so
        re-fetching would cost a round trip to produce duplicates.
        """
        user_a, group_a = team_a
        user_b, group_b = team_b

        save_locus_as_target(LOCUS, saved_by=user_a, share_with_group=group_a)

        with patch(
            "goats_tom.antares_target_save.tom_alerts_get_service_class"
        ) as mock_broker:
            save_locus_as_target(
                LOCUS, saved_by=user_b, share_with_group=group_b
            )
        mock_broker.assert_not_called()

    def test_saving_user_gets_view(self, team_a, team_b, fake_alert):
        """The individual saver, not just their group, can see the target."""
        user_a, group_a = team_a
        user_b, group_b = team_b

        save_locus_as_target(LOCUS, saved_by=user_a, share_with_group=group_a)
        target = save_locus_as_target(
            LOCUS, saved_by=user_b, share_with_group=group_b
        )
        assert "view_target" in set(get_perms(user_b, target))
