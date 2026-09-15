"""Tests for `goats_tom.pending_requests`.

The point of the registry is that one badge covers every approval flow, and
that each entry leads somewhere specific. So these check both halves: that a
user sees exactly what is waiting on *them*, and that nothing leaks from a
flow they have no part in.
"""

import pytest
from django.urls import reverse

from goats_tom import tns_membership as tm
from goats_tom.models import RegistrationRequest, TNSGroup
from goats_tom.pending_requests import pending_request_total, pending_requests
from goats_tom.tests.factories import TNSLoginFactory, UserFactory


@pytest.fixture
def tns_owner(db):
    """A user sharing one TNS group."""
    login = TNSLoginFactory(bot_name="goatsbot", group_names=["Gemini"])
    tm.sync_groups_for_login(login)
    TNSGroup.objects.filter(owner=login.user).update(allow_join_requests=True)
    return login.user


@pytest.mark.django_db
def test_nothing_pending_means_no_entries_and_no_badge():
    """An ordinary user sees no badge at all."""
    user = UserFactory()

    assert pending_requests(user) == []
    assert pending_request_total(user) == 0


@pytest.mark.django_db
def test_anonymous_user_is_handled():
    """The navbar renders for signed-out visitors too."""
    from django.contrib.auth.models import AnonymousUser

    assert pending_requests(AnonymousUser()) == []
    assert pending_request_total(AnonymousUser()) == 0


@pytest.mark.django_db
def test_tns_owner_sees_their_own_requests(tns_owner):
    """One entry, correctly worded, pointing at the page that resolves it."""
    group = TNSGroup.objects.get(owner=tns_owner)
    tm.create_join_request(UserFactory(), group)

    entries = pending_requests(tns_owner)

    assert len(entries) == 1
    assert entries[0].key == "tns"
    assert entries[0].label == "TNS Groups"
    assert entries[0].count == 1
    assert entries[0].url == reverse(
        "user-tns-login", kwargs={"pk": tns_owner.pk}
    )


@pytest.mark.django_db
def test_queue_stays_listed_when_empty(tns_owner):
    """An empty queue keeps its link, with a count of zero.

    Dropping the entry at zero would leave the only route to the queue
    appearing and vanishing depending on whether anyone had written in.
    """
    entries = pending_requests(tns_owner)

    assert [entry.key for entry in entries] == ["tns"]
    assert entries[0].count == 0
    assert pending_request_total(tns_owner) == 0


@pytest.mark.django_db
def test_account_requests_are_admin_only(tns_owner):
    """A pending signup shows for administrators and nobody else.

    A group owner with their own queue must not also see the site's
    registration queue simply because both are "requests".
    """
    RegistrationRequest.objects.create(user=UserFactory(is_active=False))
    admin = UserFactory(is_superuser=True, is_staff=True)

    assert [entry.key for entry in pending_requests(admin)] == ["account"]
    assert [entry.key for entry in pending_requests(tns_owner)] == ["tns"]


@pytest.mark.django_db
def test_total_sums_across_flows(tns_owner):
    """The badge is one number covering everything waiting on the user."""
    tns_owner.is_superuser = True
    tns_owner.save()
    RegistrationRequest.objects.create(user=UserFactory(is_active=False))
    tm.create_join_request(
        UserFactory(), TNSGroup.objects.get(owner=tns_owner)
    )

    entries = pending_requests(tns_owner)

    assert {entry.key for entry in entries} == {"account", "tns"}
    assert pending_request_total(tns_owner) == 2


@pytest.mark.django_db
def test_decided_requests_drop_out_of_the_count(tns_owner):
    """Answering a request clears it from the badge."""
    group = TNSGroup.objects.get(owner=tns_owner)
    join_request = tm.create_join_request(UserFactory(), group)

    tm.deny_join_request(join_request, decided_by=tns_owner)

    assert pending_request_total(tns_owner) == 0
    # The link survives; only the badge goes.
    assert [entry.key for entry in pending_requests(tns_owner)] == ["tns"]
