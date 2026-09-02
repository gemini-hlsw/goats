"""Tests for `custom_data_product_path`, which decides a file's storage name.

Two things are being checked, and they pull in opposite directions.

Locally the name must be **exactly** what it always was. A desktop install
is the invariant this whole effort is not allowed to break, and a changed
path there means files written where nothing looks for them.

In ``datalab`` mode the name must carry the owner, because a Django storage
backend is handed a name and nothing else. `VOSpaceStorage` can only learn
whose VOSpace to write to by reading it out of the name -- and if these two
disagree about the scheme, files are written under one name and looked for
under another.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import SuspiciousFileOperation
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.context.user_context import user_id_context
from goats_tom.tests.factories import AstroDatalabLoginFactory, UserFactory
from goats_tom.utils.utils import custom_data_product_path


@pytest.fixture
def target(db):
    """A target with a predictable name."""
    return SiderealTargetFactory.create(name="M31")


@pytest.fixture
def owner(db):
    """A user whose GOATS and Data Lab usernames differ."""
    user = UserFactory(username="goats_name")
    AstroDatalabLoginFactory(user=user, username="datalab_name")
    return user


@pytest.fixture
def record(db, target, owner):
    """An observation record with an owner."""
    return ObservationRecord.objects.create(
        target=target,
        facility="GEM",
        observation_id="GS-2026A-Q-1-1",
        parameters={},
        user=owner,
    )


@pytest.fixture
def datalab():
    """Report the storage backend as VOSpace."""
    with patch(
        "goats_tom.utils.utils._datalab_storage_enabled", return_value=True
    ):
        yield


class TestLocalMode:
    """The desktop invariant: nothing changes."""

    def test_path_with_an_observation_record(self, record, target):
        product = DataProduct(target=target, observation_record=record)
        assert (
            custom_data_product_path(product, "f.fits")
            == "M31/GEM/GS-2026A-Q-1-1/f.fits"
        )

    def test_path_without_an_observation_record(self, target):
        product = DataProduct(target=target, observation_record=None)
        assert custom_data_product_path(product, "f.fits") == "M31/none/none/f.fits"

    def test_no_owner_is_not_an_error(self, target):
        """Locally an unowned product is fine; there is only one disk.

        Notes
        -----
        The refusal in `datalab` mode is about not guessing whose *account*
        to write to. That question does not arise here, and raising would
        break manual uploads on a desktop install for no benefit.
        """
        product = DataProduct(target=target, observation_record=None)
        assert custom_data_product_path(product, "f.fits") == "M31/none/none/f.fits"


@pytest.mark.usefixtures("datalab")
class TestDatalabMode:
    """The name has to say who owns the file."""

    def test_prefixes_the_owner(self, record, target):
        assert (
            custom_data_product_path(DataProduct(target=target, observation_record=record), "f.fits")
            == "users/datalab_name/goats/M31/GEM/GS-2026A-Q-1-1/f.fits"
        )

    def test_uses_the_datalab_username_not_the_goats_one(self, record, target):
        """The two are not assumed to match.

        Notes
        -----
        `VOSpaceStorage` resolves credentials through the linked account, so
        it looks for files under the Data Lab name. Writing them under the
        GOATS name would put them somewhere nothing ever reads.
        """
        name = custom_data_product_path(
            DataProduct(target=target, observation_record=record), "f.fits"
        )
        assert name.startswith("users/datalab_name/")
        assert "goats_name" not in name

    def test_the_result_parses_as_vospace_expects(self, record, target):
        """The two halves must agree, so ask the other one.

        Notes
        -----
        This is the test that matters. `custom_data_product_path` writes the
        name and `VOSpaceStorage._split` reads it; they were written
        separately and nothing else forces them to agree.
        """
        from goats_tom.astro_data_lab import VOSpaceStorage

        name = custom_data_product_path(
            DataProduct(target=target, observation_record=record), "f.fits"
        )
        username, relative = VOSpaceStorage()._split(name)
        assert username == "datalab_name"
        assert relative == "M31/GEM/GS-2026A-Q-1-1/f.fits"

    def test_falls_back_to_the_uploader(self, target, owner):
        """A manual upload has no observation record, but has a request.

        Notes
        -----
        `custom_data_product_path` is called by Django during `save()` and
        gets only the instance and a filename, so there is no request to
        read. `UserContextMiddleware` puts the id in a `ContextVar` for
        exactly this.
        """
        product = DataProduct(target=target, observation_record=None)
        with user_id_context(owner.pk):
            assert (
                custom_data_product_path(product, "f.fits")
                == "users/datalab_name/goats/M31/none/none/f.fits"
            )

    def test_prefers_the_record_owner_over_the_uploader(self, record, target):
        """A co-I uploading to the PI's observation must not split the data.

        Notes
        -----
        The observation's owner wins because it is durable and gives the
        same answer every time. Preferring the request user would file this
        product into the co-I's storage while the rest of the observation
        sat in the PI's -- one observation across two accounts.
        """
        other = UserFactory(username="co_i")
        AstroDatalabLoginFactory(user=other, username="co_i_datalab")

        product = DataProduct(target=target, observation_record=record)
        with user_id_context(other.pk):
            name = custom_data_product_path(product, "f.fits")

        assert name.startswith("users/datalab_name/")

    def test_refuses_when_there_is_no_owner(self, target):
        """Refusing is safe; guessing is not.

        Notes
        -----
        A rejected write fails loudly and stops a download. A guessed one
        puts proprietary data in another PI's Data Lab account, and nothing
        in GOATS would notice.
        """
        product = DataProduct(target=target, observation_record=None)
        with pytest.raises(SuspiciousFileOperation):
            custom_data_product_path(product, "f.fits")

    def test_refuses_when_the_record_has_no_owner(self, target, db):
        """A NULL `user` on the record is not silently worked around.

        Notes
        -----
        This was the state of two of the three creation paths until
        `grant_observation_permissions` started recording it. If it recurs,
        this fails rather than picking somebody.
        """
        record = ObservationRecord.objects.create(
            target=target,
            facility="GEM",
            observation_id="GS-2026A-Q-1-2",
            parameters={},
        )
        product = DataProduct(target=target, observation_record=record)
        with pytest.raises(SuspiciousFileOperation):
            custom_data_product_path(product, "f.fits")

    def test_refuses_when_the_owner_has_no_datalab_account(self, target, db):
        """No linked account means no VOSpace to write to."""
        user = UserFactory(username="unlinked")
        record = ObservationRecord.objects.create(
            target=target,
            facility="GEM",
            observation_id="GS-2026A-Q-1-3",
            parameters={},
            user=user,
        )
        product = DataProduct(target=target, observation_record=record)
        with pytest.raises(SuspiciousFileOperation):
            custom_data_product_path(product, "f.fits")


class TestModeDetection:
    """Which naming scheme is in force."""

    def test_defaults_to_local(self):
        """Desktop must not opt in by accident.

        Notes
        -----
        Asks the configured backend what it is rather than reading a flag,
        so `custom_data_product_path` and `VOSpaceStorage` cannot end up
        disagreeing about the scheme in force.
        """
        from goats_tom.utils.utils import _datalab_storage_enabled

        assert _datalab_storage_enabled() is False
