"""Tests for the registration, popup, editor and routing fixes."""

import pytest
from django.test import override_settings
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.forms import RegistrationForm
from goats_tom.forms.antares_stream_subscribe import AntaresStreamSubscribeForm
from goats_tom.models import (
    AntaresDashboardMembership,
    AntaresPIGroup,
    AntaresStreamSubscription,
)


@pytest.mark.django_db()
class TestRegistrationNameRequired:
    """First and last name are mandatory on the public form."""

    def _post(self, client, **overrides):
        data = {
            "username": "namer",
            "email": "namer@example.com",
            "password1": "sufficiently-long-pw-1",
            "password2": "sufficiently-long-pw-1",
            "affiliation": "Somewhere",
            "first_name": "Ada",
            "last_name": "Lovelace",
        }
        data.update(overrides)
        return client.post(reverse("register"), data)

    def test_both_names_required(self):
        """The form itself marks them required."""
        form = RegistrationForm()
        assert form.fields["first_name"].required
        assert form.fields["last_name"].required

    def test_missing_first_name_rejected(self, client):
        """No account is created without a first name."""
        self._post(client, first_name="")
        assert not User.objects.filter(username="namer").exists()

    def test_missing_last_name_rejected(self, client):
        """Nor without a last name."""
        self._post(client, last_name="")
        assert not User.objects.filter(username="namer").exists()

    def test_complete_registration_accepted(self, client):
        """A full submission still works."""
        self._post(client)
        user = User.objects.get(username="namer")
        assert user.first_name == "Ada"
        assert user.last_name == "Lovelace"


@pytest.mark.django_db()
class TestCredentialsPopup:
    """The landing-page credential list names real services."""

    def test_lists_antares_and_rubin(self, client):
        """Both were missing despite having credential models."""
        response = client.get(reverse("home"))
        assert b"<li>ANTARES</li>" in response.content
        assert b"Rubin Science Platform" in response.content

    def test_browser_extension_not_listed(self, client):
        """The list names services, not the tools that use them."""
        response = client.get(reverse("home"))
        assert b"antares2goats" not in response.content


@pytest.mark.django_db()
class TestHandlerSkeleton:
    """The editor starts with real, editable boilerplate."""

    def test_empty_form_is_prefilled(self):
        """A fresh form seeds the skeleton as an actual value.

        Previously this was a CSS overlay drawn over Ace -- visible but not
        editable or copyable.
        """
        form = AntaresStreamSubscribeForm(user=None)
        assert form.initial["handler_code"] == form.HANDLER_CODE_SKELETON

    def test_skeleton_keeps_every_locus(self):
        """Left untouched it must not filter anything."""
        namespace = {}
        exec(AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON, namespace)
        assert namespace["myfilter"](object()) is True

    def test_toggle_defaults_off_for_a_new_subscription(self):
        """Nobody acquires a handler without asking for one."""
        form = AntaresStreamSubscribeForm(user=None)
        assert form.initial["use_handler_code"] is False

    def test_toggle_defaults_on_for_an_existing_handler(self):
        """An existing handler must not appear switched off."""
        form = AntaresStreamSubscribeForm(
            initial={"handler_code": "def myfilter(locus):\n    return False\n"},
            user=None,
        )
        assert form.initial["use_handler_code"] is True

    def test_commented_out_handler_reads_as_off(self):
        """A fully commented-out handler is a disabled one."""
        form = AntaresStreamSubscribeForm(
            initial={"handler_code": "# def myfilter(locus):\n#     return False\n"},
            user=None,
        )
        assert form.initial["use_handler_code"] is False

    def test_unticked_stores_nothing(self):
        """Without the tick, the editor's contents are ignored entirely."""
        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "handler_code": AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON,
            },
            user=None,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["handler_code"] == ""

    def test_stray_whitespace_does_not_enable_a_handler(self):
        """An accidental keystroke must not create a filter.

        Regression test: an earlier version compared the text against the
        pre-filled skeleton and treated any difference as authorship, so a
        single stray space silently gave the user a handler they never wrote.
        """
        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "handler_code": (
                    AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON + " "
                ),
            },
            user=None,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["handler_code"] == ""

    def test_ticked_stores_the_code(self):
        """With the tick, the handler is kept and validated."""
        code = "def myfilter(locus):\n    return True"
        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "use_handler_code": "on",
                "handler_code": code,
            },
            user=None,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["handler_code"] == code

    def test_ticked_still_validates(self):
        """Broken code is rejected when the handler is actually in use."""
        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "use_handler_code": "on",
                "handler_code": "def notmyfilter(locus):\n    return True",
            },
            user=None,
        )
        assert not form.is_valid()
        assert "handler_code" in form.errors

    def test_unticked_skips_validation(self):
        """Broken code is not an error if it is not going to run.

        Someone experimenting can untick and save without first having to
        make their half-written filter compile.
        """
        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "handler_code": "def notmyfilter(locus):\n    return True",
            },
            user=None,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["handler_code"] == ""

    def test_existing_handler_not_overwritten(self):
        """Seeding must never clobber real code."""
        mine = "def myfilter(locus):\n    return False\n"
        form = AntaresStreamSubscribeForm(
            initial={"handler_code": mine}, user=None
        )
        assert form.initial["handler_code"] == mine

    def test_toggle_precedes_editor_in_field_order(self):
        """Cleaning order matters: the gate must be cleaned first.

        Django cleans fields in `self.fields` order, and `clean_handler_code`
        reads the checkbox from `cleaned_data`.
        """
        names = list(AntaresStreamSubscribeForm(user=None).fields)
        assert names.index("use_handler_code") < names.index("handler_code")


@pytest.mark.django_db()
class TestRequestAccessBanner:
    """The redundant banner is gone."""

    def test_no_banner_when_everything_requested(self, client):
        """The tables below already say this, with more detail."""
        from goats_tom.antares_membership import create_join_request

        pi = User.objects.create_user("bannerpi")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-bannerpi"), pi=pi
        )
        user = User.objects.create_user("banneruser", password="pw-long-enough-1")
        create_join_request(user, pi_group)

        client.force_login(user)
        response = client.get(reverse("antares-request-access"))
        assert b"requested or joined every dashboard" not in response.content

    def test_message_kept_when_nothing_exists(self, client):
        """With no form and no tables the page would otherwise be blank."""
        user = User.objects.create_user("emptyuser", password="pw-long-enough-1")
        client.force_login(user)
        response = client.get(reverse("antares-request-access"))
        # Asserts the message survives, not its wording. The explanatory
        # clause was dropped because the reason a dashboard list is empty is
        # not a user's problem to reason about; the point of this test is
        # that the page still says something rather than rendering blank.
        assert b"no dashboards to request yet" in response.content


@pytest.mark.django_db()
class TestOwnSetupPageRoute:
    """A member can still reach their own ingestion setup."""

    @pytest.fixture()
    def member_with_access(self, db):
        """A user who can view a PI's dashboard but owns nothing."""
        pi = User.objects.create_user("routepi")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-routepi"), pi=pi
        )
        subscription = AntaresStreamSubscription.objects.create(
            owner=pi, topics=["pi_topic_zzz"]
        )
        member = User.objects.create_user("routemember", password="pw-long-enough-1")
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        return member, subscription

    def test_default_still_shows_read_only(self, client, member_with_access):
        """Unchanged: the dashboard route keeps showing the PI's config."""
        member, _ = member_with_access
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"pi_topic_zzz" in response.content

    def test_mine_shows_their_own_setup(self, client, member_with_access):
        """`?mine=1` reaches their own page, where the instructions are."""
        member, _ = member_with_access
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"), {"mine": "1"})
        assert response.status_code == 200
        assert b"pi_topic_zzz" not in response.content
        assert b'name="topics"' in response.content

    def test_broker_links_to_own_setup(self, db):
        """The ANTARES broker page must not send people to someone else's.

        Checks the source rather than rendering the broker's query form,
        which needs a full valid Elasticsearch query to render without
        errors and would be testing something unrelated.
        """
        import inspect

        from goats_tom.brokers import antares

        assert '"?mine=1"' in inspect.getsource(antares)


@pytest.mark.django_db()
class TestOwnPageBannerIsolation:
    """The user's own setup page must not report someone else's stream."""

    @pytest.fixture()
    def member_and_pi(self, db):
        """A member with view access to a PI's running subscription."""
        pi = User.objects.create_user("bannerleakpi")
        pi_group = AntaresPIGroup.objects.create(
            group=Group.objects.create(name="antares-bannerleakpi"), pi=pi
        )
        subscription = AntaresStreamSubscription.objects.create(
            owner=pi, topics=["pi_secret_topic"], is_running=True
        )
        member = User.objects.create_user(
            "bannerleakmember", password="pw-long-enough-1"
        )
        AntaresDashboardMembership.objects.create(
            pi_group=pi_group, user=member, can_view_dashboard=True
        )
        return member, subscription

    def test_own_page_shows_no_subscription(self, client, member_and_pi):
        """A member with no subscription of their own sees a blank banner."""
        member, _ = member_and_pi
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"), {"mine": "1"})
        assert b"pi_secret_topic" not in response.content

    def test_status_poll_respects_mine(self, client, member_and_pi):
        """The htmx poll must not fill the own page with the PI's state.

        Regression test: the page rendered correctly and the poll overwrote it
        three seconds later, because the status endpoint fell back to any
        dashboard the user could view.
        """
        member, _ = member_and_pi
        client.force_login(member)
        response = client.get(reverse("antares-stream-status"), {"mine": "1"})
        assert b"pi_secret_topic" not in response.content
        assert b"Currently subscribed to" not in response.content

    def test_status_poll_still_works_for_read_only(self, client, member_and_pi):
        """Without `mine`, the read-only view still reports the PI's state."""
        member, subscription = member_and_pi
        client.force_login(member)
        response = client.get(
            reverse("antares-stream-status"), {"subscription": subscription.pk}
        )
        assert b"pi_secret_topic" in response.content

    def test_own_page_poll_url_carries_mine(self, client, member_and_pi):
        """The rendered poll URL must preserve the flag.

        Otherwise the first poll drops it and the leak returns.
        """
        member, _ = member_and_pi
        client.force_login(member)
        response = client.get(reverse("antares-stream-subscribe"), {"mine": "1"})
        assert b"mine=1" in response.content


@pytest.mark.django_db()
class TestDashboardLocusCountRemoved:
    """`dashboard_locus_count()` no longer exists in any form.

    Removed when the loci limit became `AntaresStreamSubscription.max_loci`,
    enforced in `upsert_locus_row`. The count is a fact about GOATS's own
    database, and a handler running on Data Lab cannot see it -- so the same
    handler behaved differently depending on where it ran. Enforcing on the
    GOATS side also means the limit cannot be evaded by editing a staged
    handler.
    """

    def test_name_is_not_bound_in_handlers(self):
        """A handler still calling it must fail loudly, not silently pass."""
        from goats_tom.antares_locus_handler import (
            LocusHandlerRuntimeError,
            run_locus_handler,
        )

        source = (
            "def myfilter(locus):\n"
            "    return dashboard_locus_count() < 10\n"
        )
        with pytest.raises(LocusHandlerRuntimeError, match="dashboard_locus_count"):
            run_locus_handler(source, object(), subscription_id=1)

    def test_builder_is_gone(self):
        """No leftover private helper to be rebound by accident."""
        import goats_tom.antares_locus_handler as mod

        assert not hasattr(mod, "_make_dashboard_locus_count")

    def test_not_mentioned_anywhere_the_user_can_see(self):
        """Skeleton and help text must not advertise a name that is gone."""
        form = AntaresStreamSubscribeForm()
        assert "dashboard_locus_count" not in (
            AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON
        )
        assert "dashboard_locus_count" not in str(
            form.fields["handler_code"].help_text
        )


@pytest.mark.django_db()
class TestHandlerValidationIsModeDependent:
    """Handler vetting depends on where the handler will actually run.

    Locally a handler executes inside the GOATS process, on the host holding
    every user's credentials, so `import` and friends are real escapes from
    the restricted namespace. On Data Lab it runs under the PI's own account
    and quota, which is the isolation -- and handlers are *expected* to
    import from the Data Lab stack, so the ban would reject necessary code.
    """

    IMPORTS = "import math\ndef myfilter(locus):\n    return math.isfinite(locus.ra)\n"
    BROKEN = "def myfilter(locus)\n    return True\n"
    NO_FUNC = "def other(locus):\n    return True\n"

    def test_import_blocked_locally(self):
        from goats_tom.antares_locus_handler import (
            LocusHandlerError,
            check_handler_source,
        )

        with pytest.raises(LocusHandlerError, match="disallowed pattern"):
            check_handler_source(self.IMPORTS)

    @override_settings(GOATS_STREAM_EXECUTOR="datalab")
    def test_import_allowed_remotely(self):
        from goats_tom.antares_locus_handler import check_handler_source

        check_handler_source(self.IMPORTS)

    @override_settings(GOATS_STREAM_EXECUTOR="datalab")
    def test_structure_still_checked_remotely(self):
        """Syntax and `myfilter` are environment-independent, so they stay."""
        from goats_tom.antares_locus_handler import (
            LocusHandlerError,
            check_handler_source,
        )

        with pytest.raises(LocusHandlerError, match="Syntax error"):
            check_handler_source(self.BROKEN)
        with pytest.raises(LocusHandlerError, match="myfilter"):
            check_handler_source(self.NO_FUNC)

    @override_settings(GOATS_STREAM_EXECUTOR="datalab")
    def test_no_server_side_dry_run_remotely(self, monkeypatch):
        """Executing here would give both false passes and false failures."""
        import goats_tom.antares_locus_handler as mod

        ran = []
        monkeypatch.setattr(
            mod, "run_locus_handler", lambda *a, **k: ran.append(1) or True
        )
        mod.validate_handler_code("def myfilter(locus):\n    return True\n")
        assert not ran

    def test_dry_run_still_happens_locally(self, monkeypatch):
        import goats_tom.antares_locus_handler as mod

        ran = []
        monkeypatch.setattr(
            mod, "run_locus_handler", lambda *a, **k: ran.append(1) or True
        )
        mod.validate_handler_code("def myfilter(locus):\n    return True\n")
        assert ran


@pytest.mark.django_db()
class TestHelpTextAndSkeletonContent:
    """The skeleton documents the helpers; the help text stays short."""

    def test_skeleton_shows_rsp_example(self):
        """Likewise the TAP query, which is the harder one to guess."""
        skeleton = AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON
        assert "RSP_tap_service.run_async(query).to_table()" in skeleton
        assert "dp1.Object" in skeleton

    def test_skeleton_lines_fit_the_editor(self):
        """Long lines would wrap and make the examples hard to read."""
        widest = max(
            len(line)
            for line in AntaresStreamSubscribeForm.HANDLER_CODE_SKELETON.splitlines()
        )
        assert widest <= 79, f"widest line is {widest} characters"

    def test_group_suffix_help_is_concise(self):
        """It had grown to four sentences."""
        help_text = AntaresStreamSubscribeForm(user=None).fields[
            "consumer_group"
        ].help_text
        assert len(help_text) < 160
        assert "replay" in help_text
