"""Every observation record must know who owns it.

`ObservationRecord.user` was NULL on two of the three creation paths, for a
long time, without anything going visibly wrong. Nothing read the field:
scoping goes through guardian, and so does `may_reduce_observation`. The
permission rows were assigned correctly, so a PI saw and managed exactly
what they should.

`VOSpaceStorage` is the first thing that has to *name* an owner rather than
test one -- it builds a VOSpace path from a username -- and a NULL there has
no safe default. Guessing writes a PI's proprietary data into another
account.

These tests exist because the fix is one line in one function, and one line
is exactly the kind of thing a later refactor drops without noticing.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from tom_observations.models import ObservationRecord
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.permissions import grant_observation_permissions
from goats_tom.tests.factories import UserFactory


@pytest.fixture
def record(db):
    """An observation record with no owner, as upstream would create it."""
    target = SiderealTargetFactory.create()
    return ObservationRecord.objects.create(
        target=target,
        facility="GEM",
        observation_id="GS-2026A-Q-1-1",
        parameters={},
    )


@pytest.mark.django_db
class TestObservationOwnership:
    """`grant_observation_permissions` records the owner as well as granting."""

    def test_records_the_owner(self, record):
        user = UserFactory()
        grant_observation_permissions(record, user)
        record.refresh_from_db()
        assert record.user == user

    def test_grants_permissions_too(self, record):
        """Ownership and permissions are assigned together, on purpose.

        Notes
        -----
        They were separate and drifted apart: every caller granted
        permissions and none set the field. Asserting both here is what
        stops that recurring.
        """
        user = UserFactory()
        grant_observation_permissions(record, user)
        for action in ("view", "change", "delete"):
            assert user.has_perm(f"tom_observations.{action}_observationrecord", record)

    def test_does_not_overwrite_an_existing_owner(self, record):
        """Re-stamping would silently reassign somebody else's observation.

        Notes
        -----
        `ObservationCreateView` sets the owner upstream before GOATS sees
        the record, so this function is sometimes handed one that already
        has an owner.
        """
        first, second = UserFactory(), UserFactory()
        record.user = first
        record.save(update_fields=["user"])

        grant_observation_permissions(record, second)

        record.refresh_from_db()
        assert record.user == first

    @pytest.mark.parametrize("user", [None, AnonymousUser()])
    def test_tolerates_no_user(self, record, user):
        """A missing user is logged, not raised on.

        Notes
        -----
        By the time this runs the observation may already be scheduled at
        the observatory. Losing it over a database write would be far worse
        than an unstamped row an administrator can repair.
        """
        grant_observation_permissions(record, user)
        record.refresh_from_db()
        assert record.user is None

    def test_records_the_owner_in_target_permissions_only_mode(
        self, record, settings
    ):
        """Ownership is not a permission, and is recorded in either mode.

        Notes
        -----
        `TARGET_PERMISSIONS_ONLY` turns off the guardian rows because the
        target governs everything beneath it. It does not make the question
        "who made this observation" meaningless, and the storage layer needs
        an answer regardless of which permission model is in use.
        """
        settings.TARGET_PERMISSIONS_ONLY = True
        user = UserFactory()

        grant_observation_permissions(record, user)

        record.refresh_from_db()
        assert record.user == user

    def test_saves_only_the_user_field(self, record):
        """Concurrent edits to the same record must not be clobbered.

        Notes
        -----
        A full `save()` would write back every field as this instance last
        saw them, undoing anything another request changed in between --
        status updates arrive asynchronously from the facility.
        """
        user = UserFactory()
        ObservationRecord.objects.filter(pk=record.pk).update(status="COMPLETED")

        grant_observation_permissions(record, user)

        record.refresh_from_db()
        assert record.user == user
        assert record.status == "COMPLETED"
