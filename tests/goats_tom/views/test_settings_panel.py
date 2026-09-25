"""Tests that settings is the user's panel and the user list is the admin's."""

import re

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token

from goats_tom.credentials import CREDENTIAL_SERVICES
from goats_tom.models import GOALogin
from goats_tom.tests.factories import UserFactory

STORED = "fa-check fa-lg text-success"
NOT_STORED = "fa-minus fa-lg text-muted"


class TestSettingsListsCredentials(TestCase):
    """Settings is where a user manages their own service credentials."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.client.login(username="owner", password="x")

    def get_settings(self) -> str:
        """The rendered settings page of the logged-in user."""
        response = self.client.get(reverse("user-update", kwargs={"pk": self.user.pk}))
        assert response.status_code == 200
        return response.content.decode()

    def test_every_service_is_listed(self) -> None:
        """All of them, so the page is the whole picture."""
        rendered = self.get_settings()

        for label, url_name, _ in CREDENTIAL_SERVICES:
            assert label in rendered
            assert reverse(url_name, kwargs={"pk": self.user.pk}) in rendered

    def test_nothing_stored_is_reported(self) -> None:
        """A fresh account is told it has stored nothing."""
        assert self.get_settings().count(STORED) == 0

    def test_what_is_stored_is_reported(self) -> None:
        """Saving one service changes only that row."""
        GOALogin.objects.create(user=self.user, username="u", password="p")

        rendered = self.get_settings()

        assert rendered.count(STORED) == 1
        assert rendered.count(NOT_STORED) == len(CREDENTIAL_SERVICES) - 1


class TestTheUserListIsAdminOnly(TestCase):
    """The directory of accounts is an admin tool, so only admins are sent there."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")

    def get_navbar(self, user) -> str:
        """Any page renders the navbar; settings is one this user can open."""
        self.client.force_login(user)
        return self.client.get(
            reverse("user-update", kwargs={"pk": user.pk})
        ).content.decode()

    def test_an_ordinary_account_is_not_offered_it(self) -> None:
        """The whole tab is gone, not just its contents."""
        # ``reverse`` gives ``/users/``, a substring of this page's own URL, so
        # the link has to be matched as an attribute.
        assert f'href="{reverse("user-list")}"' not in self.get_navbar(self.user)

    def test_a_superuser_is_offered_it(self) -> None:
        """Administering the instance means reaching the directory."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )

        assert f'href="{reverse("user-list")}"' in self.get_navbar(admin)


class TestTheFormIsBootstrap5(TestCase):
    """GOATS is on Bootstrap 5, where upstream's markup leaves fields unspaced."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.client.login(username="owner", password="x")

    def get_settings(self) -> str:
        """The rendered settings page of the logged-in user."""
        return self.client.get(
            reverse("user-update", kwargs={"pk": self.user.pk})
        ).content.decode()

    def test_no_bootstrap_4_markup_is_left(self) -> None:
        """Bootstrap 5 dropped ``form-group``, so it spaces nothing."""
        assert "form-group" not in self.get_settings()

    def test_the_fields_carry_bootstrap_5_classes(self) -> None:
        """Every visible field is labelled and spaced."""
        rendered = self.get_settings()

        # username, first and last name, email, both passwords, affiliation.
        assert rendered.count('class="form-label"') == 7
        # Counting the whole page would also catch headings, so require only
        # that every labelled field is wrapped.
        assert rendered.count('<div class="mb-3">') >= 7

    def test_the_profile_formset_still_posts(self) -> None:
        """Rendering the formset by hand must keep its management form."""
        assert 'name="profile-TOTAL_FORMS"' in self.get_settings()


class TestTheFormStillSaves(TestCase):
    """Rendering by hand must not break the round trip."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="a-password-1")
        # Posting the login form, not ``client.login``: TOMToolkit derives the
        # credential encryption key from ``request.POST["password"]``, and
        # changing a password re-encrypts with it.
        self.client.post(
            reverse("login"), {"username": "owner", "password": "a-password-1"}
        )
        self.url = reverse("user-update", kwargs={"pk": self.user.pk})

    def submit_the_rendered_form(self, **changes: str) -> None:
        """Post back what the page renders, the way a browser would.

        Reading the fields off the page rather than hand-writing them is the
        point: it is what catches a hidden field the template forgot.
        """
        rendered = self.client.get(self.url).content.decode()
        data = {
            name: value
            for name, value in re.findall(
                r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', rendered
            )
        }
        data.pop("csrfmiddlewaretoken", None)
        data.update(changes)
        self.client.post(self.url, data)

    def test_the_profile_is_saved(self) -> None:
        """The formset is what carries affiliation, so it must come through."""
        self.submit_the_rendered_form(
            first_name="Owner",
            email="owner@example.org",
            **{"profile-0-affiliation": "NOIRLab"},
        )

        self.user.refresh_from_db()
        assert self.user.first_name == "Owner"
        assert self.user.profile.affiliation == "NOIRLab"

    def test_the_password_can_be_changed(self) -> None:
        """This page is the only way a user changes their own password."""
        self.submit_the_rendered_form(
            email="owner@example.org",
            password1="a-new-password-1",
            password2="a-new-password-1",
        )

        self.user.refresh_from_db()
        assert self.user.check_password("a-new-password-1")


class TestEveryAccountFormRendersTheSame(TestCase):
    """Settings, the credential pages and change-password share one partial."""

    def setUp(self) -> None:
        self.admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(self.admin)

    def get(self, url: str) -> str:
        """The rendered page at `url`."""
        response = self.client.get(url)
        assert response.status_code == 200
        return response.content.decode()

    def test_the_credential_pages_are_bootstrap_5(self) -> None:
        """These are the pages every user reaches from settings."""
        rendered = self.get(reverse("user-goa-login", kwargs={"pk": self.admin.pk}))

        assert "form-group" not in rendered
        assert rendered.count('class="form-label"') == 2

    def test_the_credential_pages_do_not_repeat_a_class(self) -> None:
        """Their widgets already carry ``form-control``, so it must not double."""
        rendered = self.get(reverse("user-goa-login", kwargs={"pk": self.admin.pk}))

        assert "form-control form-control" not in rendered

    def test_the_change_password_page_is_bootstrap_5(self) -> None:
        """Changing your own password skips the confirmation and shows the form."""
        rendered = self.get(
            reverse("admin-user-change-password", kwargs={"pk": self.admin.pk})
        )

        assert "form-group" not in rendered
        assert rendered.count('class="form-label"') == 2


class TestTheFieldOrderIsGroupedByMeaning(TestCase):
    """Who you are, then how you sign in, then what you may do."""

    def labels_of(self, user) -> list[str]:
        """The field labels of `user`'s settings page, in rendered order."""
        self.client.force_login(user)
        rendered = self.client.get(
            reverse("user-update", kwargs={"pk": user.pk})
        ).content.decode()
        # Checkbox groups label differently, so match the class loosely.
        return re.findall(r'class="form-label[^"]*"[^>]*>([^<]+)<', rendered)

    def test_an_ordinary_account(self) -> None:
        """Affiliation belongs with the name and email, not after the passwords."""
        user = UserFactory(username="owner", password="x")

        assert self.labels_of(user) == [
            "Username",
            "First name",
            "Last name",
            "Email",
            "Affiliation",
            "Password",
            "Password confirmation",
        ]

    def test_a_superuser_gets_groups_last(self) -> None:
        """Groups is administration, and only an admin sees it at all."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )

        assert self.labels_of(admin)[-1] == "Groups"


class TestCheckboxesAreBootstrap5(TestCase):
    """Django renders checkbox groups as bare inputs inside their labels."""

    def setUp(self) -> None:
        Group.objects.create(name="observers")
        self.admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(self.admin)

    def test_the_group_checkboxes_are_styled(self) -> None:
        """Only a superuser sees the field at all."""
        rendered = self.client.get(
            reverse("user-update", kwargs={"pk": self.admin.pk})
        ).content.decode()

        assert 'class="form-check"' in rendered
        assert "form-check-input" in rendered
        assert 'class="form-check-label"' in rendered


class TestTheApiTokenIsOnlyShownToItsOwner(TestCase):
    """The token is a bearer credential: reading it is acting as that user."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        # TOMToolkit creates one on ``post_save``, so there is already a token.
        self.token = Token.objects.get(user=self.user)
        self.admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )

    def settings_of(self, user) -> str:
        """The rendered settings page of `user`, as this client sees it."""
        return self.client.get(
            reverse("user-update", kwargs={"pk": user.pk})
        ).content.decode()

    def test_you_can_read_your_own(self) -> None:
        """You have to be able to copy it into the antares2goats extension."""
        self.client.force_login(self.user)

        assert self.token.key in self.settings_of(self.user)

    def test_an_administrator_cannot_read_it(self) -> None:
        """They can replace it without ever seeing it."""
        self.client.force_login(self.admin)

        rendered = self.settings_of(self.user)

        assert self.token.key not in rendered
        assert reverse("regenerate-api-token", kwargs={"pk": self.user.pk}) in rendered

    def test_regenerating_your_own_shows_the_new_one(self) -> None:
        """The HTMX re-render passes a thinner context, so this is its own case."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("regenerate-api-token", kwargs={"pk": self.user.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.user.refresh_from_db()
        assert Token.objects.get(user=self.user).key in response.content.decode()

    def test_the_button_never_says_revoke(self) -> None:
        """The endpoint always creates a replacement, so it does not revoke."""
        self.client.force_login(self.admin)

        rendered = self.settings_of(self.user)

        assert "Revoke" not in rendered
        assert "Regenerate API Token" in rendered

    def test_an_administrator_leaves_the_user_with_a_working_token(self) -> None:
        """Naming this "revoke" would be a lie: they end up able to call the API."""
        self.client.force_login(self.admin)
        old_key = self.token.key

        self.client.post(
            reverse("regenerate-api-token", kwargs={"pk": self.user.pk}),
            HTTP_HX_REQUEST="true",
        )

        assert Token.objects.get(user=self.user).key != old_key
