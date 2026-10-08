"""Tests for the TNS sharing views.

All TNS access management lives on one page -- the TNS credential page at
`user-tns-login` -- so most of these exercise that. The rest cover what the
views add on top of `goats_tom.tns_membership`: ownership enforced by the
lookup rather than a separate check, the report page refusing targets the
user cannot see, and a user with no credentials being offered the groups
they could ask to join rather than told to go and register a bot.
"""

import re

import pytest
from django.conf import settings
from django.test import override_settings
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
        bot_id="42", bot_name="goatsbot", groups=["Gemini", "Private"]
    )
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


def settings_payload(*rows):
    """Build the POST data for the group settings formset.

    Parameters
    ----------
    *rows : tuple
        One ``(group, allow_join_requests, recommended_authors)`` per row, in
        the order `goats_tom.tns_membership.owned_groups` returns them, with
        an optional fourth element giving the group a new name.

    Returns
    -------
    dict
        Management form plus one prefixed row per group.
    """
    data = {
        "form-TOTAL_FORMS": str(len(rows)),
        "form-INITIAL_FORMS": str(len(rows)),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        group, allow, authors = row[:3]
        # A fourth element renames the group; without one it keeps its name.
        name = row[3] if len(row) > 3 else group.name
        data[f"form-{index}-id"] = str(group.pk)
        data[f"form-{index}-name"] = name
        data[f"form-{index}-recommended_authors"] = authors
        if allow:
            data[f"form-{index}-allow_join_requests"] = "on"
    return data


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
def test_a_message_over_the_limit_is_rejected(client, owner, shared_group):
    member = UserFactory()
    client.force_login(member)

    client.post(
        reverse("tns-request-access"),
        {"tns_group": shared_group.pk, "message": "x" * 501},
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
    assert b"Who can report under your groups" in response.content
    assert b"Ada Lovelace" in response.content


@pytest.mark.django_db
def test_usernames_are_never_shown(client, owner, shared_group):
    """A requester's username must not reach the page.

    A username is half of a login credential and identifies nobody to a
    colleague, so it is never the right thing to display -- including when no
    full name is set, where `custom_filters.display_name` falls back to the
    email address, and to a dash only when there is not one either.
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
    assert b"Who can report under your groups" not in response.content


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
    stranger = TNSLoginFactory(groups=["Elsewhere"])
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
    """Only the owner decides whether their own bot is shared.

    The endpoint saves every group at once, so it takes no primary key from
    the URL and ownership rests on the queryset: a posted row naming somebody
    else's group is not in the acting user's `owned_groups`, so the formset
    resolves no instance for it and saves nothing.
    """
    member = UserFactory()
    client.force_login(member)

    client.post(
        reverse("tns-group-settings"),
        settings_payload((shared_group, True, "Me")),
    )

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
        reverse("tns-group-settings"),
        settings_payload(
            (shared_group, False, "A. Smith (NOIRLab)"),
            (TNSGroup.objects.get(owner=owner, name="Private"), False, ""),
        ),
    )

    shared_group.refresh_from_db()
    assert not shared_group.allow_join_requests
    assert tm.posting_options(member)


@pytest.mark.django_db
@pytest.mark.parametrize("target_permissions_only", [True, False])
@pytest.mark.parametrize("endpoint", ["report-tns", "submit-report", "submit-classify"])
def test_tns_page_refuses_a_target_the_user_cannot_see(
    client, owner, target, target_permissions_only, endpoint
):
    """Upstream's permission mixin never runs on this view, so GOATS checks.

    Pairing "any target by primary key" with "somebody else's credentials"
    is exactly what an owner is trusting GOATS not to allow.
    """
    client.force_login(owner)

    target.permissions = Target.Permissions.PRIVATE
    target.save()
    with override_settings(TARGET_PERMISSIONS_ONLY=target_permissions_only):
        method = client.get if endpoint == "report-tns" else client.post
        response = method(reverse(f"tom_tns:{endpoint}", kwargs={"pk": target.pk}))

    # `tom_common.middleware.Raise403Middleware` turns every 403 into a bounce
    # to the login page. The refusal is the same; only its presentation is.
    # This becomes a plain 403 when `PermissionDeniedMiddleware` lands.
    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)


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
        {"posting_option": f"owner:{owner.pk}"},
    )

    assert client.session[SESSION_KEY] == f"owner:{owner.pk}"


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
def test_a_revoked_member_sees_removed_not_declined(client, owner, shared_group):
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    membership = TNSGroupMembership.objects.get(user=member)
    client.force_login(owner)
    client.post(
        reverse("tns-revoke-membership", kwargs={"pk": membership.pk})
    )
    client.force_login(member)

    response = client.get(reverse("user-tns-login", kwargs={"pk": member.pk}))

    assert b"Removed" in response.content
    assert b"Declined" not in response.content


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


@pytest.mark.django_db
def test_the_group_author_map_is_parseable_json(client, owner, target):
    """The script block the author field reads must survive autoescaping.

    Rendering a pre-dumped JSON string into a `<script>` turns every quote
    into `&quot;`, which the browser does not decode there, so `JSON.parse`
    throws and the author list silently stops following the group -- the
    failure is invisible because the script swallows the exception.
    """
    import json

    assign_perm("tom_targets.view_target", owner, target)
    client.force_login(owner)

    html = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    ).content.decode()

    marker = 'id="tns-group-authors"'
    assert marker in html
    block = html.split(marker, 1)[1].split(">", 1)[1].split("</script>", 1)[0]
    authors = json.loads(block)
    assert authors["Gemini"] == "A. Smith (NOIRLab)"


@pytest.mark.django_db
def test_submitting_without_credentials_is_refused(client, target):
    """The endpoint must not fall through to the instance-wide bot.

    A user with no credentials of their own and no granted group reaches
    `tom_tns`'s submit view otherwise, which reads the bot out of
    ``settings.BROKERS`` -- so anyone signed in could post under it, and the
    audit row would name no owner at all.
    """
    from goats_tom.models import TNSSubmissionRecord

    nobody = UserFactory()
    assign_perm("tom_targets.view_target", nobody, target)
    client.force_login(nobody)

    response = client.post(
        reverse("tom_tns:submit-report", kwargs={"pk": target.pk}),
        {"object_name": "GOATS1"},
    )

    # `Raise403Middleware` turns the refusal into a bounce to the login page.
    assert response.status_code == 302
    assert response.url.startswith(settings.LOGIN_URL)
    assert not TNSSubmissionRecord.objects.exists()


@pytest.mark.django_db
def test_switching_bots_renders_with_new_credentials(client, owner, shared_group, target, mocker) -> None:
    from goats_tom.middleware import tns

    member_login = TNSLoginFactory(bot_id="99", groups=["Own"])
    member = member_login.user
    TNSGroupMembership.objects.create(user=member, tns_group=shared_group)
    assign_perm("tom_targets.view_target", member, target)
    client.force_login(member)
    session = client.session
    session[SESSION_KEY] = "own"
    session.save()
    payload_spy = mocker.spy(tns, "payload_for_option")

    response = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk}),
        {"posting_option": f"owner:{owner.pk}"},
        follow=True,
    )

    assert response.status_code == 200
    assert len(response.redirect_chain) == 1
    assert response.context["active_option"].owner == owner
    assert payload_spy.spy_return["bot_id"] == "42"
    assert payload_spy.spy_return["group_names"] == ["Gemini"]
    assert b"A. Smith (NOIRLab)" in response.content


@pytest.mark.django_db
def test_existing_login_groups_appear_on_credentials_page(client) -> None:
    login = TNSLoginFactory(groups=["LegacyGroup"])
    client.force_login(login.user)

    response = client.get(reverse("user-tns-login", kwargs={"pk": login.user.pk}))

    assert response.status_code == 200
    assert [
        form.instance.name
        for form in response.context["group_settings"]
        if form.instance.pk
    ] == ["LegacyGroup"]
    assert not TNSGroup.objects.get(owner=login.user).allow_join_requests


@pytest.mark.django_db
def test_one_save_updates_every_group(client, owner, shared_group, private_group):
    """The settings table posts once for all of a user's groups.

    The page used to render a form and a Save button per group, so changing
    two groups meant two round trips and two success messages.
    """
    client.force_login(owner)

    client.post(
        reverse("tns-group-settings"),
        settings_payload(
            (shared_group, False, "C. Author (NOIRLab)"),
            (private_group, True, "D. Author (ESO)"),
        ),
    )

    shared_group.refresh_from_db()
    private_group.refresh_from_db()
    assert not shared_group.allow_join_requests
    assert shared_group.recommended_authors == "C. Author (NOIRLab)"
    assert private_group.allow_join_requests
    assert private_group.recommended_authors == "D. Author (ESO)"


def rendered_field(content, name):
    """Return the value rendered inside a named textarea.

    Parameters
    ----------
    content : str
        The rendered page.
    name : str
        The field's form name.

    Returns
    -------
    str
        Its initial value, or ``""`` when the field is not on the page.
    """
    match = re.search(
        rf'<textarea[^>]*name="{name}"[^>]*>(.*?)</textarea>', content, re.S
    )
    return match.group(1).strip() if match else ""


def posted_settings(content):
    """Rebuild the settings formset payload from a rendered page.

    Parameters
    ----------
    content : str
        The rendered credential page.

    Returns
    -------
    dict
        Every ``form-`` prefixed control the page rendered, with the value it
        was rendered with. Unchecked boxes come back empty, which is what a
        browser would leave out and `forms.BooleanField` reads as `False`.
    """
    data = {}
    for tag in re.findall(r"<(?:input|textarea)[^>]*>", content):
        name = re.search(r'name="([^"]+)"', tag)
        if name is None or not name.group(1).startswith("form-"):
            continue
        value = re.search(r'value="([^"]*)"', tag)
        data[name.group(1)] = value.group(1) if value else ""
    return data


@pytest.mark.django_db
def test_the_settings_table_saves_what_the_page_rendered(
    client, owner, shared_group, private_group
):
    """The rendered table carries everything the endpoint needs.

    A formset is only as good as its wiring: drop the management form or a
    row's hidden primary key and the page still renders, while saving
    silently does nothing. Posting the page back to itself is what notices.
    """
    client.force_login(owner)
    url = reverse("user-tns-login", kwargs={"pk": owner.pk})

    data = posted_settings(client.get(url).content.decode())
    # Gemini is the open one in the fixture, so this closes one group and
    # opens the other in a single post.
    data.pop("form-0-allow_join_requests", None)
    data["form-1-allow_join_requests"] = "on"
    data["form-1-recommended_authors"] = "E. Author (Gemini)"
    client.post(reverse("tns-group-settings"), data)

    shared_group.refresh_from_db()
    private_group.refresh_from_db()
    assert not shared_group.allow_join_requests
    assert private_group.allow_join_requests
    assert private_group.recommended_authors == "E. Author (Gemini)"


@pytest.mark.django_db
def test_a_user_without_a_full_name_is_shown_by_email(client, owner, shared_group):
    """An unset name falls back to the email, not to a dash.

    Most accounts are created without a first or last name, so a dash there
    was the common case rather than the exception, and it named nobody.
    """
    member = UserFactory(first_name="", last_name="", email="ada@noirlab.edu")
    tm.create_join_request(member, shared_group)
    client.force_login(owner)

    content = client.get(
        reverse("user-tns-login", kwargs={"pk": owner.pk})
    ).content.decode()

    assert "ada@noirlab.edu" in content
    assert member.username not in content


@pytest.mark.django_db
def test_a_superuser_cannot_change_another_users_group_settings(
    client, owner, shared_group
):
    """Holding the keys to the install is not the same as owning the bot.

    `BaseLoginView.dispatch` lets a superuser open somebody else's credential
    page, because administering a stored secret is their job. Deciding who may
    report under that person's bot name is not: the endpoint scopes its
    queryset to the acting user, so the row is not theirs to save whatever
    their privileges.
    """
    superuser = UserFactory(is_superuser=True, is_staff=True)
    client.force_login(superuser)

    client.post(
        reverse("tns-group-settings"),
        settings_payload((shared_group, True, "Hijacked")),
    )

    shared_group.refresh_from_db()
    assert shared_group.recommended_authors == "A. Smith (NOIRLab)"


@pytest.mark.django_db
def test_several_groups_can_be_added_in_one_save(
    client, owner, shared_group, private_group
):
    """The table takes as many new rows as the page chose to render.

    The Add button clones a row per click before anything is posted, so a
    save carries every group the user typed rather than one per round trip.
    """
    client.force_login(owner)
    data = settings_payload(
        (shared_group, True, ""), (private_group, False, "")
    )
    data["form-TOTAL_FORMS"] = "5"
    for index, name in enumerate(["GOTO", "ZTF", "ATLAS"], start=2):
        data[f"form-{index}-name"] = name
        data[f"form-{index}-recommended_authors"] = ""

    client.post(reverse("tns-group-settings"), data)

    assert sorted(
        TNSGroup.objects.filter(owner=owner).values_list("name", flat=True)
    ) == ["ATLAS", "GOTO", "Gemini", "Private", "ZTF"]


@pytest.mark.django_db
def test_the_blank_row_adds_a_group(client, owner, shared_group, private_group):
    """A group comes into being by being typed into the table's last row."""
    client.force_login(owner)
    data = settings_payload(
        (shared_group, True, "A. Smith (NOIRLab)"), (private_group, False, "")
    )
    data["form-TOTAL_FORMS"] = "3"
    data["form-2-name"] = "GOTO"
    data["form-2-recommended_authors"] = ""

    client.post(reverse("tns-group-settings"), data)

    added = TNSGroup.objects.get(owner=owner, name="GOTO")
    assert not added.allow_join_requests


@pytest.mark.django_db
def test_renaming_a_group_through_the_page_keeps_its_members(
    client, owner, shared_group, private_group
):
    """Correcting a name must not revoke the people approved for it.

    The whole reason groups became rows: while the name was the identity,
    fixing a typo in it silently cut off everyone who had been approved.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    client.force_login(owner)

    client.post(
        reverse("tns-group-settings"),
        settings_payload(
            (shared_group, True, "", "Gemini-North"), (private_group, False, "")
        ),
    )

    shared_group.refresh_from_db()
    assert shared_group.name == "Gemini-North"
    assert TNSGroupMembership.objects.filter(
        user=member, tns_group=shared_group
    ).exists()


@pytest.mark.django_db
def test_removing_a_group_revokes_the_access_it_granted(
    client, owner, shared_group, private_group
):
    """Deleting a group takes its memberships with it, by design.

    Unlike a rename, this is the deliberate act of withdrawing a group, so
    the cascade is right -- the page says how many people it affects before
    the box is ticked.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    client.force_login(owner)

    data = settings_payload((shared_group, True, ""), (private_group, False, ""))
    data["form-0-DELETE"] = "on"
    client.post(reverse("tns-group-settings"), data)

    assert not TNSGroup.objects.filter(pk=shared_group.pk).exists()
    assert not TNSGroupMembership.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_each_group_shows_how_many_people_share_it(
    client, owner, shared_group
):
    """"Shared with" says who is using a group, and what removing it costs.

    A column rather than a warning under the remove box: it answers "which
    of my groups is anyone actually using?" whether or not a removal is in
    mind, and it still sits in the row before the box is ticked, which is
    what makes the cascade a deliberate act.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    client.force_login(owner)

    content = client.get(
        reverse("user-tns-login", kwargs={"pk": owner.pk})
    ).content.decode()

    assert "Shared with" in content
    count = re.search(r'<td class="text-center">\s*(\d+)\s*</td>', content)
    assert count is not None and count.group(1) == "1"


@pytest.mark.django_db
def test_two_rows_cannot_name_the_same_group(
    client, owner, shared_group, private_group
):
    """Names differing only in case would split one group's settings in two.

    The model's unique constraint covers ``(owner, name)`` exactly, and TNS
    treats the name as one group however it is typed.
    """
    client.force_login(owner)

    response = client.post(
        reverse("tns-group-settings"),
        settings_payload(
            (shared_group, True, ""), (private_group, False, "", "gemini")
        ),
        follow=True,
    )

    private_group.refresh_from_db()
    assert private_group.name == "Private"
    # Named rather than merely refused: the redirect drops the bound
    # formset, so an error rendered on the row itself would never be seen.
    told = " ".join(str(message) for message in response.context["messages"])
    assert "'gemini' is listed twice." in told


@pytest.mark.django_db
def test_the_page_carries_what_the_add_button_needs(client, owner, shared_group):
    """The Add button clones a row, and a rename would silence it.

    It reads the row template, the body it appends to and the management
    form's total, all by id. Miss one and the button does nothing at all,
    with no error anywhere -- which no other test would notice.
    """
    client.force_login(owner)

    content = client.get(
        reverse("user-tns-login", kwargs={"pk": owner.pk})
    ).content.decode()

    row_template = re.search(
        r'<template id="tns-group-row">(.*?)</template>', content, re.S
    )
    assert row_template is not None
    # `__prefix__` is what the script swaps for the next row number.
    assert 'name="form-__prefix__-name"' in row_template.group(1)
    assert 'placeholder="Add a group"' in row_template.group(1)
    assert 'id="id_form-TOTAL_FORMS"' in content
    assert 'id="tns-group-rows"' in content


@pytest.mark.django_db
def test_the_author_list_matches_the_group_the_page_selects(client, owner, target):
    """The seeded authors belong to the group shown selected, not another.

    `tom_tns` gives `reporting_group` no initial, so the browser selects the
    first option. Seeding from the first group that happened to have authors
    offered one group's name beside another group's author list, and only
    touching the dropdown corrected it -- so accepting the default sent the
    mismatch to a public record.
    """
    first = TNSGroup.objects.get(owner=owner, name="Gemini")
    first.recommended_authors = ""
    first.save()
    later = TNSGroup.objects.get(owner=owner, name="Private")
    later.recommended_authors = "Z. Wrong (Nowhere)"
    later.save()
    assign_perm("tom_targets.view_target", owner, target)
    client.force_login(owner)

    content = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    ).content.decode()

    # The field, not the page: the group-to-authors map the script uses is
    # also rendered here and legitimately carries every group's list.
    assert "Z. Wrong (Nowhere)" not in rendered_field(content, "reporter")


@pytest.mark.django_db
def test_a_group_without_authors_credits_the_submitter(client, owner, target):
    """An empty author list falls back to a name, never to "Anonymous User".

    `tom_tns` asks for ``getattr(user, "get_full_name()", ...)`` -- the call
    parentheses are inside the attribute name -- so upstream credits every
    pre-filled report to "Anonymous User" whatever the account is called.
    """
    TNSGroup.objects.filter(owner=owner).update(recommended_authors="")
    owner.first_name, owner.last_name = "Ada", "Lovelace"
    owner.save()
    assign_perm("tom_targets.view_target", owner, target)
    client.force_login(owner)

    content = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    ).content.decode()

    assert rendered_field(content, "reporter").startswith("Ada Lovelace, using")
    assert "Anonymous User" not in content


@pytest.mark.django_db
def test_the_page_can_restore_the_credit_when_the_group_changes(
    client, owner, target
):
    """The fallback rides on the widget, so switching group can put it back.

    Without it the script blanked the field, which showed something
    different from what that same group showed on first render.
    """
    owner.first_name, owner.last_name = "Ada", "Lovelace"
    owner.save()
    assign_perm("tom_targets.view_target", owner, target)
    client.force_login(owner)

    content = client.get(
        reverse("tom_tns:report-tns", kwargs={"pk": target.pk})
    ).content.decode()

    assert 'data-default-authors="Ada Lovelace, using' in content


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["approve", "deny"])
def test_the_confirmation_never_names_the_username(
    client, owner, shared_group, action
):
    """The toast follows the same rule as the table it appears over.

    The page is careful to show a full name, then an email, then a dash --
    and the message that came back the moment a button was pressed printed
    the username, which is half of a login credential.
    """
    member = UserFactory(
        first_name="Ada", last_name="Lovelace", email="ada@noirlab.edu"
    )
    join_request = tm.create_join_request(member, shared_group)
    client.force_login(owner)

    response = client.post(
        reverse("tns-decide-join-request", kwargs={"pk": join_request.pk}),
        {"action": action},
        follow=True,
    )

    told = " ".join(str(message) for message in response.context["messages"])
    assert "Ada Lovelace" in told
    assert member.username not in told


@pytest.mark.django_db
def test_revoking_never_names_the_username(client, owner, shared_group):
    """Same rule, and the name has to be read before the row is deleted."""
    member = UserFactory(first_name="Ada", last_name="Lovelace")
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    membership = TNSGroupMembership.objects.get(user=member)
    client.force_login(owner)

    response = client.post(
        reverse("tns-revoke-membership", kwargs={"pk": membership.pk}),
        follow=True,
    )

    told = " ".join(str(message) for message in response.context["messages"])
    assert "Ada Lovelace" in told
    assert member.username not in told


@pytest.mark.django_db
def test_groups_are_listed_as_a_person_would_sort_them(client, owner):
    """Capitals must not jump the queue.

    The database's default collation compares bytes, so every capitalised
    name sorted above every lowercase one and "GOTO" appeared before
    "Gemini" in a list somebody reads.
    """
    TNSGroup.objects.create(owner=owner, name="GOTO")
    TNSGroup.objects.create(owner=owner, name="alerce")

    assert [group.name for group in tm.owned_groups(owner)] == [
        "alerce",
        "Gemini",
        "GOTO",
        "Private",
    ]


@pytest.mark.django_db
def test_a_closed_group_still_counts_the_people_in_it(client, owner, shared_group):
    """Closing a group does not revoke anyone, so the count stays a number.

    "Shared with" reads as a dash only where the question does not arise --
    a closed group nobody is in. A dash on a closed group that still has
    members would hide access that exists.
    """
    member = UserFactory()
    tm.approve_join_request(
        tm.create_join_request(member, shared_group), decided_by=owner
    )
    shared_group.allow_join_requests = False
    shared_group.save()
    client.force_login(owner)

    content = client.get(
        reverse("user-tns-login", kwargs={"pk": owner.pk})
    ).content.decode()

    count = re.search(r'<td class="text-center">\s*(\d+)\s*</td>', content)
    assert count is not None and count.group(1) == "1"
