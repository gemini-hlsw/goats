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


class TestTheUserListIsForAdministrators(TestCase):
    """Nobody else can reach it: settings is where a user finds their own."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.other = UserFactory(username="other", password="y")

    def test_an_ordinary_account_is_refused(self) -> None:
        """The page carries every account's name, email and join date."""
        self.client.login(username="owner", password="x")

        response = self.client.get(reverse("user-list"))

        assert response.status_code == 302
        assert response["Location"].startswith(reverse("login"))

    def test_a_superuser_is_offered_every_row(self) -> None:
        """The admin flow stays reachable from the list."""
        admin = UserFactory(
            username="admin", password="z", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)

        rendered = self.client.get(reverse("user-list")).content.decode()

        assert reverse("user-goa-login", kwargs={"pk": self.other.pk}) in rendered
        assert reverse("user-goa-login", kwargs={"pk": admin.pk}) in rendered


class TestEditIsOfferedOnYourOwnRow(TestCase):
    """The list is an administrator's, so every row carries its actions."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.other = UserFactory(username="zzcolleague", password="y")

    def get_user_list(self) -> str:
        """The rendered user list, as this client sees it."""
        return self.client.get(reverse("user-list")).content.decode()

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
