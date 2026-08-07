"""Tests for what happens to ANTARES records when a target is deleted.

Targets are shared between teams rather than duplicated -- one `Target` per
locus, with access granted to each team that asks to save it. That makes
deletion a cross-team action, and it makes the leftover bookkeeping rows a
correctness problem rather than untidiness.
"""

import pytest
from django.contrib.auth.models import User
from django.db import transaction
from tom_targets.models import Target

from goats_tom.antares_target_save import (
    SharedTargetDeletionError,
    is_shared_target,
    target_saver_usernames,
)
from goats_tom.models import (
    AntaresStreamSubscription,
    AntaresTargetSave,
    GeminiTriggerRecord,
)

LOCUS = "ANT2026del"


@pytest.fixture()
def target(db):
    return Target.objects.create(name=LOCUS, type=Target.SIDEREAL, ra=1.0, dec=2.0)


@pytest.fixture()
def pi_one(db):
    return User.objects.create_user("pi_one")


@pytest.fixture()
def pi_two(db):
    return User.objects.create_user("pi_two")


def _save_record(user):
    return AntaresTargetSave.objects.create(locus_id=LOCUS, saved_by=user)


@pytest.mark.django_db()
class TestSharedTargetsAreProtected:
    """A target held by two teams cannot be deleted by either."""

    def test_one_team_can_delete(self, target, pi_one):
        _save_record(pi_one)

        assert is_shared_target(target) is False
        target.delete()

        assert not Target.objects.filter(name=LOCUS).exists()

    def test_two_teams_cannot(self, target, pi_one, pi_two):
        """Deleting would remove it from a team that never asked."""
        _save_record(pi_one)
        _save_record(pi_two)

        assert is_shared_target(target) is True
        assert target_saver_usernames(target) == ["pi_one", "pi_two"]

        # Wrapped in its own atomic block so the refusal rolls back to a
        # savepoint rather than poisoning the test's transaction -- see the
        # note in `goats_tom.signals.block_shared_target_deletion`.
        with pytest.raises(SharedTargetDeletionError), transaction.atomic():
            target.delete()

        assert Target.objects.filter(name=LOCUS).exists()

    def test_the_refusal_names_the_teams(self, target, pi_one, pi_two):
        """The PI cannot see other teams' dashboards, so the message must say."""
        _save_record(pi_one)
        _save_record(pi_two)

        with pytest.raises(SharedTargetDeletionError) as excinfo, transaction.atomic():
            target.delete()

        message = str(excinfo.value)
        assert "pi_one" in message
        assert "pi_two" in message

    def test_a_target_nobody_saved_can_be_deleted(self, target):
        """Not every target came from ANTARES."""
        assert is_shared_target(target) is False
        target.delete()

        assert not Target.objects.filter(name=LOCUS).exists()


@pytest.mark.django_db()
class TestDeletingATargetClearsItsRecords:
    """Deleting an unshared target is a genuine clean slate."""

    def test_save_and_trigger_records_both_go(self, target, pi_one):
        """The trigger record used to outlive the target.

        It keys on `locus_id` with no link to the target, and a record blocks
        any further trigger for that locus in the run -- so a deleted target
        left the locus untriggerable with nothing on screen to explain it.
        """
        subscription = AntaresStreamSubscription.objects.create(
            owner=pi_one, topics=["t"], generation=2
        )
        _save_record(pi_one)
        GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id=LOCUS,
            generation=2,
            status=GeminiTriggerRecord.STATUS_FAILED,
        )

        target.delete()

        assert not AntaresTargetSave.objects.filter(locus_id=LOCUS).exists()
        assert not GeminiTriggerRecord.objects.filter(locus_id=LOCUS).exists()

    def test_records_for_other_loci_are_untouched(self, target, pi_one):
        subscription = AntaresStreamSubscription.objects.create(
            owner=pi_one, topics=["t"]
        )
        _save_record(pi_one)
        GeminiTriggerRecord.objects.create(
            subscription=subscription, locus_id="ANT_OTHER", generation=0
        )

        target.delete()

        assert GeminiTriggerRecord.objects.filter(locus_id="ANT_OTHER").exists()

    def test_a_blocked_deletion_leaves_records_intact(
        self, target, pi_one, pi_two
    ):
        """The refusal rolls back inside the deletion's transaction.

        `pre_delete` and `post_delete` both fire during the same cascade, so a
        cleanup that ran before the refusal would otherwise destroy the very
        records proving the target is shared.
        """
        subscription = AntaresStreamSubscription.objects.create(
            owner=pi_one, topics=["t"]
        )
        _save_record(pi_one)
        _save_record(pi_two)
        GeminiTriggerRecord.objects.create(
            subscription=subscription, locus_id=LOCUS, generation=0
        )

        with pytest.raises(SharedTargetDeletionError), transaction.atomic():
            target.delete()

        assert AntaresTargetSave.objects.filter(locus_id=LOCUS).count() == 2
        assert GeminiTriggerRecord.objects.filter(locus_id=LOCUS).exists()


@pytest.mark.django_db()
class TestDeleteViewRefusesBeforeDestroyingAnything:
    """The view must check first, not rely on the signal.

    `TargetDeleteView.form_valid` tears down observation records before
    deleting the target. Leaving the refusal to `pre_delete` would mean those
    are already gone by the time the deletion is rejected.
    """

    def test_the_check_precedes_the_teardown(self):
        import inspect

        from goats_tom.views.target_delete import TargetDeleteView

        source = inspect.getsource(TargetDeleteView.form_valid)

        assert source.index("target_saver_usernames") < source.index(
            "ObservationRecord.objects.filter"
        )
