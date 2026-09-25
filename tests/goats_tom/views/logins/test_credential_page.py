"""Tests the credential page's title and its panel of the other services."""

from django.test import TestCase
from django.urls import reverse

from goats_tom.credentials import CREDENTIAL_SERVICES
from goats_tom.models import GOALogin
from goats_tom.tests.factories import UserFactory

STORED = "fa-check fa-lg text-success"
NOT_STORED = "fa-minus fa-lg text-muted"


class TestTheTitleComesFromTheRegistry(TestCase):
    """The service names live in one place, not in a chain of template ifs."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        self.client.login(username="owner", password="x")

    def render(self, url_name: str) -> str:
        """The rendered credential page at `url_name`."""
        return self.client.get(
            reverse(url_name, kwargs={"pk": self.user.pk})
        ).content.decode()

    def test_the_long_name_is_shown_with_the_short_one(self) -> None:
        """Both are useful when the short name is the one people say."""
        assert (
            "Manage Gemini Observatory Archive (GOA) Credentials"
            in self.render("user-goa-login")
        )

    def test_a_name_that_is_already_long_is_not_repeated(self) -> None:
        """Astro Data Lab has no separate short name to put in brackets."""
        rendered = self.render("user-astro-data-lab-login")

        assert "Manage Astro Data Lab Credentials" in rendered
        assert "Astro Data Lab (Astro Data Lab)" not in rendered


class TestThePanelOfOtherServices(TestCase):
    """Moving between services should not need a trip back to settings."""

    def setUp(self) -> None:
        self.user = UserFactory(username="owner", password="x")
        GOALogin.objects.create(user=self.user, username="u", password="p")
        self.client.login(username="owner", password="x")
        self.rendered = self.client.get(
            reverse("user-astro-data-lab-login", kwargs={"pk": self.user.pk})
        ).content.decode()

    def test_every_service_is_listed(self) -> None:
        """The list must not change shape as you move between services."""
        for label, _, _ in CREDENTIAL_SERVICES:
            assert label in self.rendered

    def test_the_page_you_are_on_offers_no_link_to_itself(self) -> None:
        """Four services are reachable from here; this one already is here."""
        here = reverse("user-astro-data-lab-login", kwargs={"pk": self.user.pk})

        # Once for the form action, never as a link in the panel.
        assert self.rendered.count(f'href="{here}"') == 0

    def test_the_others_are_reachable(self) -> None:
        """That is the whole point of the panel."""
        for _, url_name, _ in CREDENTIAL_SERVICES:
            if url_name == "user-astro-data-lab-login":
                continue
            assert reverse(url_name, kwargs={"pk": self.user.pk}) in self.rendered

    def test_what_is_stored_is_reported(self) -> None:
        """One service has credentials, so exactly one row says so."""
        assert self.rendered.count(STORED) == 1
        assert self.rendered.count(NOT_STORED) == len(CREDENTIAL_SERVICES) - 1
