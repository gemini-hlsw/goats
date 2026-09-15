"""Tests for the TNS sharing views.

All TNS access management lives on one page -- the TNS credential page at
`user-tns-login` -- so most of these exercise that. The rest cover what the
views add on top of `goats_tom.tns_membership`: ownership enforced by the
lookup rather than a separate check, the report page refusing targets the
user cannot see, and a user with no credentials being offered the groups
they could ask to join rather than told to go and register a bot.
"""

import pytest
from django.urls import reverse
from guardian.shortcuts import assign_perm
from tom_targets.models import Target

from goats_tom import tns_membership as tm
from goats_tom.middleware.tns import SESSION_KEY
from goats_tom.models import TNSGroup, TNSGroupJoinRequest, TNSGroupMembership
from goats_tom.tests.factories import TNSLoginFactory, UserFactory


@pytest.fixture
def target(db):
    """A saved target, visible to nobody in particular."""
    return Target.objects.create(name="GOATS1", ra=10.0, dec=-20.0)


@pytest.fixture
def owner(db):
    """An owner sharing one group and keeping another to themselves."""
    login = TNSLoginFactory(
        bot_id="42", bot_name="goatsbot", group_names=["Gemini", "Private"]
    )
    tm.sync_groups_for_login(login)
    TNSGroup.objects.filter(owner=login.user, name="Gemini").update(
        allow_join_requests=True,
        recommended_authors="A. Smith (NOIRLab)",
    )
    return login.user


@pytest.fixture
def shared_group(owner):
    return TNSGroup.objects.get(owner=owner, name="Gemini")


@pytest.fixture
def private_group(owner):
    return TNSGroup.objects.get(owner=owner, name="Private")


@pytest.mark.django_db
def test_credential_page_offers_only_shared_groups(client, owner, shared_group):
    """The request dropdown offers the shared group and not the private one."""
    member = UserFactory()
    client.force_login(member)

    response = client.get(
        reverse("user-tns-login", kwargs={"pk": member.pk})
    )

    assert response.status_code == 200
    assert b"Gemini" in response.content
    assert b"Private" not in response.content


@pytest.mark.django_db
def test_requesting_access_creates_a_pending_request(
    client, owner, shared_group
):
    member = UserFactory()
    client.force_login(member)

    client.post(
        reverse("tns-request-access"),
        {"tns_group": shared_group.pk, "message": "ToO programme"},
    )

    join_request = TNSGroupJoinRequest.objects.get(requester=member)
    assert join_request.status == TNSGroupJoinRequest.STATUS_PENDING
    assert join_request.tns_group == shared_group


@pytest.mark.django_db
def test_cannot_request_a_group_never_offered(client, owner, private_group):
    """A group not open to requests is rejected, not merely hidden.

    The dropdown never offers it, so reaching here means the group id was
    submitted directly.
    """
    member = UserFactory()
    client.force_login(member)

    client.post(
        reverse("tns-request-access"),
        {"tns_group": private_group.pk, "message": ""},
    )

    assert not TNSGroupJoinRequest.objects.filter(requester=member).exists()


@pytest.mark.django_db
def test_request_endpoint_rejects_get(client):
    """It is a POST endpoint, not a page -- the pages were consolidated."""
    client.force_login(UserFactory())

    assert client.get(reverse("tns-request-access")).status_code == 405


@pytest.mark.django_db
def test_owner_sees_requests_and_members_on_their_credential_page(
    client, owner, shared_group
):
    """The one page answers "who is asking" and "who already has access"."""
    member = UserFactory(first_name="Ada", last_name="Lovelace")
    tm.create_join_request(member, shared_group)
    client.force_login(owner)

    response = client.get(reverse("user-tns-login", kwargs={"pk": owner.pk}))

    assert response.status_code == 200
    assert b"Requests to your groups" in response.content
    assert b"Ada Lovelace" in response.content


@pytest.mark.django_db
def test_usernames_are_never_shown(client, owner, shared_group):
    """A requester's username must not reach the page.

    A username is half of a login credential and identifies nobody to a
    colleague, so it is never the right thing to display -- including when
    no full name is set, where the cell shows a dash instead.
    """
    member = UserFactory(first_name="", last_name="")
    tm.create_join_request(member, shared_group)
    client.force_login(owner)

    response = client.get(reverse("user-tns-login", kwargs={"pk": owner.pk}))

    assert member.username.encode() not in response.content


@pytest.mark.django_db
def test_superuser_cannot_manage_another_users_sharing(
    client, owner, shared_group
):
    """Administering a stored secret is not the same as deciding sharing.

    A superuser may open someone else's credential page, but approving a
    request there would decide whose reports go out under that user's bot
    name.
    """
    superuser = UserFactory(is_superuser=True, is_staff=True)
    member = UserFactory()
    tm.create_join_request(member, shared_group)
    client.force_login(superuser)

    response = client.get(reverse("user-tns-login", kwargs={"pk": owner.pk}))

    assert response.status_code == 200
    assert b"Requests to your groups" not in response.content


@pytest.mark.django_db
def test_owner_can_approve_a_request(client, owner, shared_group):
    member = UserFactory()
    join_request = tm.create_join_request(member, shared_group)
    client.force_login(owner)

    client.post(
        reverse("tns-decide-join-request", kwargs={"pk": join_request.pk}),
        {"action": "approve"},
    )

    join_request.refresh_from_db()
    assert join_request.status == TNSGroupJoinRequest.STATUS_APPROVED
    assert TNSGroupMembership.objects.filter(
        user=member, tns_group=shared_group
    ).exists()


@pytest.mark.django_db
def test_a_stranger_cannot_decide_someone_elses_request(
    client, owner, shared_group
):
    """The lookup is scoped to the acting user's own groups.

    Guessing a primary key gets a 404, because ownership is enforced by the
    query rather than by a check that could be skipped.
    """
    member = UserFactory()
    join_request = tm.create_join_request(member, shared_group)
    stranger = TNSLoginFactory(group_names=["Elsewhere"])
    tm.sync_groups_for_login(stranger)
    client.force_login(stranger.user)

    response = client.post(
        reverse("tns-decide-join-request", kwargs={"pk": join_request.pk}),
        {"action": "approve"},
    )

    assert response.status_code == 404
    join_request.refresh_from_db()
    assert join_request.status == TNSGroupJoinRequest.STATUS_PENDING


@pytest.mark.django_db
def test_a_member_cannot_change_the_owners_group_settings(
    client, owner, shared_group
):
    """Only the owner decides whether their own bot is shared."""
    member = UserFactory()
    client.force_login(member)

    response = client.post(
        reverse("tns-group-settings", kwargs={"pk": shared_group.pk}),
        {"allow_join_requests": "on", "recommended_authors": "Me"},
    )

    assert response.status_code == 404
    shared_group.refresh_from_db()
    assert shared_group.recommended_authors == "A. Smith (NOIRLab)"


@pytest.mark.django_db
def test_closing_a_group_does_not_revoke_existing_members(
    client, owner, shared_group
):
    """The toggle governs new requests, not access somebody already relies on."""
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    client.force_login(owner)

    client.post(
        reverse("tns-group-settings", kwargs={"pk": shared_group.pk}),
        {"recommended_authors": "A. Smith (NOIRLab)"},
    )

    shared_group.refresh_from_db()
    assert not shared_group.allow_join_requests
    assert tm.posting_options(member)


@pytest.mark.django_db
def test_tns_page_refuses_a_target_the_user_cannot_see(client, owner, target):
    """Upstream's permission mixin never runs on this view, so GOATS checks.

    Pairing "any target by primary key" with "somebody else's credentials"
    is exactly what an owner is trusting GOATS not to allow.
    """
    client.force_login(owner)

    response = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_tns_page_offers_groups_to_a_user_without_credentials(
    client, owner, shared_group, target
):
    """No credentials but a shared group available means an invitation.

    Telling this user to go and register their own bot would send them to
    do work they do not need to do.
    """
    member = UserFactory()
    assign_perm("tom_targets.view_target", member, target)
    client.force_login(member)

    response = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    )

    assert response.status_code == 200
    assert b"Request access" in response.content
    assert b"Gemini" in response.content


@pytest.mark.django_db
def test_choosing_an_option_is_remembered_across_requests(
    client, owner, shared_group, target
):
    """The picker writes to the session, which is what the submit view reads.

    `tom_tns` posts its forms to its own endpoints, so a query parameter set
    on the page would be dropped before reaching the request that needs it.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    assign_perm("tom_targets.view_target", member, target)
    client.force_login(member)

    client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk}),
        {"posting_option": f"group:{shared_group.pk}"},
    )

    assert client.session[SESSION_KEY] == f"group:{shared_group.pk}"


@pytest.mark.django_db
def test_owner_can_revoke_a_membership(client, owner, shared_group):
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    membership = TNSGroupMembership.objects.get(user=member)
    client.force_login(owner)

    client.post(
        reverse("tns-revoke-membership", kwargs={"pk": membership.pk})
    )

    assert not TNSGroupMembership.objects.filter(pk=membership.pk).exists()
    assert tm.posting_options(member) == []


@pytest.mark.django_db
def test_bot_name_is_shown_to_a_member(client, owner, shared_group):
    """A member sees the bot their reports will be attributed to.

    The bot name is what appears on the public TNS record, so somebody
    about to submit under it needs to know what it is.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    client.force_login(member)

    response = client.get(reverse("user-tns-login", kwargs={"pk": member.pk}))

    assert b"goatsbot" in response.content


@pytest.mark.django_db
def test_bot_name_is_hidden_while_a_request_is_pending(
    client, owner, shared_group
):
    """A pending request means no access, so no bot name."""
    member = UserFactory()
    tm.create_join_request(member, shared_group)
    client.force_login(member)

    response = client.get(reverse("user-tns-login", kwargs={"pk": member.pk}))

    assert b"Gemini" in response.content
    assert b"goatsbot" not in response.content


@pytest.mark.django_db
def test_navbar_badge_counts_only_your_own_pending_requests(
    owner, shared_group
):
    """The count covers groups you own and nobody else's.

    This badge is what a PI returning from an observing run actually sees;
    the toast sent at request time reaches only a connected session.
    """
    from goats_tom.pending_requests import pending_request_total

    member = UserFactory()
    stranger = UserFactory()
    tm.create_join_request(member, shared_group)

    assert pending_request_total(owner) == 1
    assert pending_request_total(stranger) == 0
    assert pending_request_total(member) == 0


@pytest.mark.django_db
def test_submission_log_shows_the_full_name_not_the_username(client, owner):
    """The log identifies the sender by name, never by login handle."""
    from goats_tom.models import TNSSubmissionRecord

    sender = UserFactory(first_name="Ada", last_name="Lovelace")
    TNSSubmissionRecord.objects.create(
        submitted_by=sender,
        display_name=sender.get_full_name(),
        username=sender.username,
        owner=owner,
        kind=TNSSubmissionRecord.KIND_REPORT,
        object_name="AT2026aaa",
        succeeded=True,
    )
    client.force_login(owner)

    response = client.get(reverse("user-tns-login", kwargs={"pk": owner.pk}))

    assert b"Ada Lovelace" in response.content
    assert sender.username.encode() not in response.content
