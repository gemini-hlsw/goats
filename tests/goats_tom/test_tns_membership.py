"""Tests for `goats_tom.tns_membership`.

The cases that matter most here are the negative ones. Sharing a TNS bot
means one user's submission goes out under another user's name, so the
question these tests keep asking is not "does the happy path work" but
"can a grant be made to cover more than it was meant to".
"""

import pytest
from django.db import IntegrityError, transaction

from goats_tom import tns_membership as tm
from goats_tom.middleware.tns import payload_for_option
from goats_tom.models import (
    TNSGroup,
    TNSGroupJoinRequest,
    TNSGroupMembership,
)
from goats_tom.tests.factories import TNSLoginFactory, UserFactory


@pytest.fixture
def owner_with_groups():
    """An owner whose bot posts to three groups, one of them shared.

    Returns
    -------
    tuple
        ``(user, login, shared_group, private_group)``.
    """
    login = TNSLoginFactory(
        bot_id="42",
        bot_name="goatsbot",
        group_names=["Gemini", "SCAT", "Private"],
    )
    tm.sync_groups_for_login(login)
    shared = TNSGroup.objects.get(owner=login.user, name="Gemini")
    shared.allow_join_requests = True
    shared.recommended_authors = "A. Smith (NOIRLab), B. Jones (Gemini)"
    shared.save()
    private = TNSGroup.objects.get(owner=login.user, name="Private")
    return login.user, login, shared, private


@pytest.mark.django_db
def test_sync_creates_a_row_per_name():
    """Saving credentials creates one group row per listed name."""
    login = TNSLoginFactory(group_names=["Gemini", " Gemini ", "SCAT", ""])
    tm.sync_groups_for_login(login)

    names = sorted(
        TNSGroup.objects.filter(owner=login.user).values_list("name", flat=True)
    )
    assert names == ["Gemini", "SCAT"]


@pytest.mark.django_db
def test_sync_does_not_opt_anything_in():
    """Groups are never shared as a side effect of saving credentials."""
    login = TNSLoginFactory(group_names=["Gemini"])
    tm.sync_groups_for_login(login)

    assert not TNSGroup.objects.get(owner=login.user).allow_join_requests


@pytest.mark.django_db
def test_resaving_credentials_preserves_settings(owner_with_groups):
    """Re-saving credentials must not reset a curated group.

    A user editing an unrelated field -- rotating the API key, say --
    would otherwise silently revoke sharing and wipe the author list.
    """
    _, login, shared, _ = owner_with_groups

    tm.sync_groups_for_login(login)

    shared.refresh_from_db()
    assert shared.allow_join_requests
    assert "Smith" in shared.recommended_authors


@pytest.mark.django_db
def test_dropping_a_name_hides_the_group_without_deleting_it(
    owner_with_groups,
):
    """Removing a name stops offering the group but keeps its settings.

    Deleting the row would cascade away every membership granted through
    it, so a typo corrected a minute later would revoke everyone's access.
    """
    _, login, shared, _ = owner_with_groups
    member = UserFactory()

    login.group_names = ["SCAT"]
    login.save()
    tm.sync_groups_for_login(login)

    assert TNSGroup.objects.filter(pk=shared.pk).exists()
    assert list(tm.requestable_groups(member)) == []


@pytest.mark.django_db
def test_only_opted_in_groups_are_requestable(owner_with_groups):
    """A group with the toggle off is never offered."""
    _, _, shared, _ = owner_with_groups
    member = UserFactory()

    assert [group.name for group in tm.requestable_groups(member)] == [
        shared.name
    ]


@pytest.mark.django_db
def test_owner_is_not_offered_their_own_group(owner_with_groups):
    """An owner cannot request a group they already own."""
    owner, _, _, _ = owner_with_groups

    assert list(tm.requestable_groups(owner)) == []


@pytest.mark.django_db
def test_cannot_request_a_group_that_is_not_shared(owner_with_groups):
    """Requesting an opted-out group is refused, not merely hidden."""
    _, _, _, private = owner_with_groups
    member = UserFactory()

    with pytest.raises(tm.TNSJoinRequestError):
        tm.create_join_request(member, private)


@pytest.mark.django_db
def test_user_without_credentials_or_grants_cannot_post():
    """Someone with neither credentials nor a membership has no options."""
    assert tm.posting_options(UserFactory()) == []
    assert tm.resolve_posting_option(UserFactory(), None) is None


@pytest.mark.django_db
def test_second_pending_request_is_rejected(owner_with_groups):
    """The partial unique constraint stops a duplicate pending request."""
    _, _, shared, _ = owner_with_groups
    member = UserFactory()

    tm.create_join_request(member, shared)

    with pytest.raises(tm.TNSJoinRequestError):
        tm.create_join_request(member, shared)


@pytest.mark.django_db
def test_can_request_again_after_a_denial(owner_with_groups):
    """A denial must not bar somebody permanently.

    This is why the uniqueness constraint is conditional on `pending`
    rather than covering the pair outright.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()

    first = tm.create_join_request(member, shared)
    tm.deny_join_request(first, decided_by=owner)

    second = tm.create_join_request(member, shared)
    assert second.status == TNSGroupJoinRequest.STATUS_PENDING


@pytest.mark.django_db
def test_duplicate_membership_is_rejected(owner_with_groups):
    """One membership per user per group, enforced by the database."""
    _, _, shared, _ = owner_with_groups
    member = UserFactory()

    TNSGroupMembership.objects.create(tns_group=shared, user=member)

    with pytest.raises(IntegrityError), transaction.atomic():
        TNSGroupMembership.objects.create(tns_group=shared, user=member)


@pytest.mark.django_db
def test_approval_grants_exactly_one_group(owner_with_groups):
    """An approved member gets the owner's bot, scoped to the one group.

    One option, because an option is a bot -- and its `groups` is what the
    "Reporting group" dropdown will offer.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()

    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=owner
    )

    options = tm.posting_options(member)
    assert len(options) == 1
    assert options[0].groups == (shared,)
    assert "goatsbot" in options[0].label


@pytest.mark.django_db
def test_forged_option_key_cannot_select_an_unheld_group(owner_with_groups):
    """A hand-edited key for the owner's *other* group must not be honoured.

    The key travels in the session, which the user controls, so this is the
    check standing between "may post as Gemini" and "may post as anything
    that bot can reach".
    """
    owner, _, shared, private = owner_with_groups
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=owner
    )

    resolved = tm.resolve_posting_option(member, f"owner:{owner.pk}")

    assert resolved.groups == (shared,)


@pytest.mark.django_db
def test_payload_uses_owners_bot_but_only_the_granted_group(
    owner_with_groups,
):
    """The submission carries the owner's key, scoped to one group.

    `tom_tns` builds its reporting-group dropdown from `group_names`, so a
    full list here would let a member pick any of the owner's groups.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=owner
    )

    payload = payload_for_option(tm.resolve_posting_option(member, None))

    assert payload["bot_id"] == "42"
    assert payload["group_names"] == [shared.name]
    assert "Smith" in payload["recommended_authors"]
    assert payload["group_authors"] == {shared.name: shared.recommended_authors}


@pytest.mark.django_db
def test_owner_gets_one_option_covering_all_their_groups(owner_with_groups):
    """The owner has one bot, so one option, offering all three groups."""
    owner, _, _, _ = owner_with_groups

    options = tm.posting_options(owner)

    assert [option.key for option in options] == ["own"]
    assert {group.name for group in options[0].groups} == {
        "Gemini",
        "SCAT",
        "Private",
    }


@pytest.mark.django_db
def test_revocation_takes_effect_immediately(owner_with_groups):
    """A revoked member loses the option on their very next request.

    Resolution runs against live membership rather than anything cached in
    the session, so an already-open page cannot keep posting.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=owner
    )

    tm.revoke_membership(TNSGroupMembership.objects.get(user=member))

    assert tm.posting_options(member) == []
    assert tm.resolve_posting_option(member, f"owner:{owner.pk}") is None


@pytest.mark.django_db
def test_group_is_not_offered_once_owner_deletes_credentials(
    owner_with_groups,
):
    """A grant survives, but an unusable group is never offered.

    `TNSGroup` outlives the credentials it describes on purpose, so
    "opted in" and "usable" are different questions.
    """
    owner, login, shared, _ = owner_with_groups
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared), decided_by=owner
    )

    login.delete()

    assert TNSGroupMembership.objects.filter(user=member).exists()
    assert tm.posting_options(member) == []


@pytest.mark.django_db
def test_deciding_an_already_decided_request_is_refused(owner_with_groups):
    """A request can only be decided once."""
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()
    join_request = tm.create_join_request(member, shared)
    tm.approve_join_request(join_request, decided_by=owner)

    with pytest.raises(tm.TNSJoinRequestError):
        tm.deny_join_request(join_request, decided_by=owner)
