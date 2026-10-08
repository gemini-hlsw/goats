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
        groups=["Gemini", "SCAT", "Private"],
    )
    shared = TNSGroup.objects.get(owner=login.user, name="Gemini")
    shared.allow_join_requests = True
    shared.recommended_authors = "A. Smith (NOIRLab), B. Jones (Gemini)"
    shared.save()
    private = TNSGroup.objects.get(owner=login.user, name="Private")
    return login.user, login, shared, private


@pytest.mark.django_db
def test_a_new_group_starts_closed():
    """Adding a group never exposes a bot on its own."""
    login = TNSLoginFactory(groups=["Gemini"])

    assert not TNSGroup.objects.get(owner=login.user).allow_join_requests


@pytest.mark.django_db
def test_resaving_credentials_leaves_the_groups_alone(owner_with_groups):
    """Rotating an API key must not reset a curated group.

    Structural rather than something the save has to be careful about:
    credentials and groups are separate records, so one cannot overwrite the
    other.
    """
    _, login, shared, _ = owner_with_groups

    login.token = "rotated"
    login.save()

    shared.refresh_from_db()
    assert shared.allow_join_requests
    assert "Smith" in shared.recommended_authors


@pytest.mark.django_db
def test_renaming_a_group_keeps_its_members(owner_with_groups):
    """A rename is an edit the memberships survive.

    This is the reason groups are rows. While the name was the identity --
    an entry in a list of strings on the login -- correcting a typo in it
    silently revoked everyone who had been approved for the old spelling.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()
    tm.approve_join_request(tm.create_join_request(member, shared), decided_by=owner)

    shared.name = "Gemini-North"
    shared.save()

    granted = [
        group.name for option in tm.posting_options(member) for group in option.groups
    ]
    assert granted == ["Gemini-North"]


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
def test_revocation_marks_the_approved_request_revoked(owner_with_groups):
    """The request behind a revoked membership records the removal.

    Left approved, the member's page read it as a decline dated from the
    approval.
    """
    owner, _, shared, _ = owner_with_groups
    member = UserFactory()
    join_request = tm.create_join_request(member, shared)
    tm.approve_join_request(join_request, decided_by=owner)
    approved_at = TNSGroupJoinRequest.objects.get(pk=join_request.pk).decided_at

    tm.revoke_membership(
        TNSGroupMembership.objects.get(user=member), revoked_by=owner
    )

    join_request.refresh_from_db()
    assert join_request.status == TNSGroupJoinRequest.STATUS_REVOKED
    assert join_request.decided_by == owner
    assert join_request.decided_at > approved_at
    # Revoked is not pending, so the member may ask again.
    assert shared in tm.requestable_groups(member)


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


@pytest.mark.django_db
def test_your_own_bot_files_under_every_group_you_have() -> None:
    """The own option carries all of the owner's groups, shared or not.

    Sharing governs who else may use the bot, never what its owner may file
    under.
    """
    login = TNSLoginFactory(groups=["Gemini", "SCAT"])

    option = tm.resolve_posting_option(login.user, "own")

    assert payload_for_option(option)["group_names"] == ["Gemini", "SCAT"]


@pytest.mark.django_db
def test_other_users_pending_request_does_not_block_reapplication(owner_with_groups) -> None:
    _, _, group, _ = owner_with_groups
    requester = UserFactory()
    TNSGroupJoinRequest.objects.create(
        tns_group=group, requester=requester, status=TNSGroupJoinRequest.STATUS_DENIED
    )
    TNSGroupJoinRequest.objects.create(tns_group=group, requester=UserFactory())

    assert tm.requestable_groups(requester).filter(pk=group.pk).exists()

    TNSGroupJoinRequest.objects.create(tns_group=group, requester=requester)
    assert not tm.requestable_groups(requester).filter(pk=group.pk).exists()
