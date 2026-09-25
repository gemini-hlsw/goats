"""Tests that a credential page only ever writes its own user's credentials."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from goats_tom.models import GOALogin
from goats_tom.tests.factories import UserFactory
from goats_tom.views import GOALoginView


@patch.object(GOALoginView, "perform_login_and_logout", return_value=True)
class TestCredentialOwnership(TestCase):
    """The user list links to everyone's credential pages, so the view checks."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.other = UserFactory(username="other", password="y")
        GOALogin.objects.create(
            user=self.other, username="other_goa", password="other_pass"
        )
        self.client.login(username="owner", password="x")

    def url_for(self, user: User) -> str:
        """The GOA credential page of `user`."""
        return reverse("user-goa-login", kwargs={"pk": user.pk})

    def test_saving_your_own_credentials_works(self, _mock) -> None:
        """The ordinary case is untouched."""
        self.client.post(
            self.url_for(self.user), {"username": "mine", "password": "mine_pass"}
        )

        assert GOALogin.objects.get(user=self.user).username == "mine"

    def test_another_users_credentials_are_not_overwritten(self, _mock) -> None:
        """Posting to somebody else's page must leave their credentials alone."""
        self.client.post(
            self.url_for(self.other), {"username": "pwned", "password": "pwned_pass"}
        )

        login = GOALogin.objects.get(user=self.other)
        assert login.username == "other_goa"
        assert login.password == "other_pass"

    def test_another_users_page_cannot_be_opened(self, _mock) -> None:
        """The form is not even rendered for somebody else's account."""
        response = self.client.get(self.url_for(self.other))

        # ``Raise403Middleware`` turns the ``PermissionDenied`` into a redirect.
        assert response.status_code == 302

    def test_a_superuser_may_manage_another_user(self, _mock) -> None:
        """The admin flow the user list offers keeps working."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)

        self.client.post(
            self.url_for(self.other), {"username": "set_by_admin", "password": "p"}
        )

        assert GOALogin.objects.get(user=self.other).username == "set_by_admin"


@patch.object(GOALoginView, "perform_login_and_logout", return_value=True)
class TestCredentialManagerIsOffered(TestCase):
    """The user list only offers the credential manager where it would work."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.other = UserFactory(username="other", password="y")

    def get_user_list(self) -> str:
        """The rendered user list, as this client sees it."""
        return self.client.get(reverse("user-list")).content.decode()

    def test_your_own_row_offers_it(self, _mock) -> None:
        """Everyone can reach their own credentials."""
        self.client.login(username="owner", password="x")

        assert reverse("user-goa-login", kwargs={"pk": self.user.pk}) in (
            self.get_user_list()
        )

    def test_another_users_row_does_not(self, _mock) -> None:
        """A link that only leads to a refusal is not offered."""
        self.client.login(username="owner", password="x")

        assert reverse("user-goa-login", kwargs={"pk": self.other.pk}) not in (
            self.get_user_list()
        )

    def test_a_superuser_is_offered_every_row(self, _mock) -> None:
        """The admin flow stays reachable from the list."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)

        rendered = self.get_user_list()
        assert reverse("user-goa-login", kwargs={"pk": self.other.pk}) in rendered
        assert reverse("user-goa-login", kwargs={"pk": admin.pk}) in rendered


class TestUserListShowsOnlyYou(TestCase):
    """The user list carries names and emails, so it is not a directory."""

    def setUp(self) -> None:
        self.user = UserFactory(
            username="owner", password="x", email="owner@example.org"
        )
        # A name no page furniture could contain, so the assertion is meaningful.
        self.other = UserFactory(
            username="zzcolleague", password="y", email="zzcolleague@example.org"
        )

    def get_user_list(self) -> str:
        """The rendered user list, as this client sees it."""
        return self.client.get(reverse("user-list")).content.decode()

    def test_an_ordinary_account_sees_only_itself(self) -> None:
        """Another user's name and email must not be on the page."""
        self.client.login(username="owner", password="x")

        rendered = self.get_user_list()

        assert "owner@example.org" in rendered
        assert "zzcolleague" not in rendered

    def test_a_superuser_sees_everyone(self) -> None:
        """Administering the instance means seeing who is on it."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)

        rendered = self.get_user_list()

        assert "owner@example.org" in rendered
        assert "zzcolleague@example.org" in rendered


class TestEditIsOfferedOnYourOwnRow(TestCase):
    """Changing your own password goes through the Edit form, so it is offered."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.other = UserFactory(username="zzcolleague", password="y")

    def get_user_list(self) -> str:
        """The rendered user list, as this client sees it."""
        return self.client.get(reverse("user-list")).content.decode()

    def test_your_own_row_offers_edit(self) -> None:
        """An ordinary account can reach its own settings from the list."""
        self.client.login(username="owner", password="x")

        assert reverse("user-update", kwargs={"pk": self.user.pk}) in (
            self.get_user_list()
        )

    def test_the_admin_password_button_is_not_offered(self) -> None:
        """`UserPasswordChangeView` is superuser-only, so the link would refuse."""
        self.client.login(username="owner", password="x")

        assert reverse(
            "admin-user-change-password", kwargs={"pk": self.user.pk}
        ) not in (self.get_user_list())

    def test_a_superuser_is_offered_both(self) -> None:
        """The admin columns stay as they were."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)

        rendered = self.get_user_list()
        assert reverse("user-update", kwargs={"pk": self.other.pk}) in rendered
        assert (
            reverse("admin-user-change-password", kwargs={"pk": self.other.pk})
            in rendered
        )
