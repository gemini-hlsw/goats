"""Tests for the "already stored" indicator on credential pages."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from goats_tom.models import (
    AntaresKafkaLogin,
    GOALogin,
    GPPLogin,
    RSPTapLogin,
    TNSLogin,
)


@pytest.fixture()
def user(db):
    """A signed-in user managing their own credentials."""
    return User.objects.create_user("credowner", password="pw-long-enough-1")


@pytest.mark.django_db()
class TestStoredIndicator:
    """The page must say whether anything is stored."""

    def test_not_stored_by_default(self, client, user):
        """A fresh account shows no credentials stored."""
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b"Not stored" in response.content
        assert b">Stored<" not in response.content

    def test_stored_after_saving(self, client, user):
        """Once saved, the badge says so.

        Previously the page looked identical either way, so the only way to
        find out was to save something -- which overwrote whatever was there.
        """
        AntaresKafkaLogin.objects.create(
            user=user, api_key="k", api_secret="s"
        )
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b">Stored<" in response.content

    def test_button_says_update_when_stored(self, client, user):
        """The button should reflect that submitting replaces."""
        AntaresKafkaLogin.objects.create(
            user=user, api_key="k", api_secret="s"
        )
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b"Update ANTARES Kafka Credentials" in response.content

    def test_button_says_save_when_absent(self, client, user):
        """And "Save" when there is nothing to replace."""
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b"Save ANTARES Kafka Credentials" in response.content

    def test_replacement_warning_only_when_stored(self, client, user):
        """The warning is meaningless with nothing stored."""
        client.force_login(user)
        url = reverse("user-antares-kafka-login", args=[user.pk])
        assert b"Submitting replaces" not in client.get(url).content

        AntaresKafkaLogin.objects.create(
            user=user, api_key="k", api_secret="s"
        )
        assert b"Submitting replaces" in client.get(url).content

    def test_secret_is_never_rendered(self, client, user):
        """No part of the secret may appear, not even masked.

        These are stored in plain text, so a partial reveal narrows the
        search space while telling the user nothing the badge does not.
        """
        AntaresKafkaLogin.objects.create(
            user=user,
            api_key="verysecretkeyvalue",
            api_secret="verysecretsecretvalue",
        )
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b"verysecretkeyvalue" not in response.content
        assert b"verysecretsecretvalue" not in response.content

    def test_form_fields_stay_empty(self, client, user):
        """Nothing is pre-filled, so a partial edit cannot be re-saved."""
        AntaresKafkaLogin.objects.create(
            user=user, api_key="storedkey", api_secret="storedsecret"
        )
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b'value="storedkey"' not in response.content


@pytest.mark.django_db()
class TestCredentialTimestamps:
    """Every credential type records when it was stored."""

    @pytest.mark.parametrize(
        ("model", "kwargs"),
        [
            (AntaresKafkaLogin, {"api_key": "k", "api_secret": "s"}),
            (GOALogin, {"username": "u", "password": "p"}),
            (GPPLogin, {"token": "t"}),
            (TNSLogin, {"token": "t"}),
            (RSPTapLogin, {"access_token": "t"}),
        ],
    )
    def test_timestamps_set_on_create(self, model, kwargs):
        """Defined once on the abstract base, so all types get them."""
        user = User.objects.create_user(f"ts{model.__name__}")
        record = model.objects.create(user=user, **kwargs)
        assert record.created_at is not None
        assert record.updated_at is not None

    def test_updated_at_advances_on_save(self):
        """Answers "how stale is this?" for a returning user."""
        user = User.objects.create_user("tsadvance")
        record = AntaresKafkaLogin.objects.create(
            user=user, api_key="k", api_secret="s"
        )
        first = record.updated_at
        record.api_key = "k2"
        record.save()
        record.refresh_from_db()
        assert record.updated_at > first

    def test_last_updated_shown_on_page(self, client, user):
        """The date reaches the page, not just the database."""
        AntaresKafkaLogin.objects.create(
            user=user, api_key="k", api_secret="s"
        )
        client.force_login(user)
        response = client.get(
            reverse("user-antares-kafka-login", args=[user.pk])
        )
        assert b"Last updated" in response.content


@pytest.mark.django_db()
class TestIndicatorAppliesToAllServices:
    """The shared template means every service benefits."""

    @pytest.mark.parametrize(
        ("url_name", "model", "kwargs"),
        [
            ("user-goa-login", GOALogin, {"username": "u", "password": "p"}),
            ("user-gpp-login", GPPLogin, {"token": "t"}),
            ("user-tns-login", TNSLogin, {"token": "t"}),
            ("user-rsp-tap-login", RSPTapLogin, {"access_token": "t"}),
        ],
    )
    def test_badge_on_each_service(self, client, user, url_name, model, kwargs):
        """Not just the ANTARES page."""
        client.force_login(user)
        url = reverse(url_name, args=[user.pk])
        assert b"Not stored" in client.get(url).content

        model.objects.create(user=user, **kwargs)
        assert b">Stored<" in client.get(url).content


@pytest.mark.django_db()
class TestIngestionHelpText:
    """The ingestion page states its prerequisite and how to get it."""

    def test_links_to_own_credentials_and_antares_team(self, client, user):
        """The credential page and a way to request a key must both be there.

        The email was previously mentioned only as prose ("the ANTARES team"),
        leaving a user with no key nowhere to go.
        """
        client.force_login(user)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"mailto:antares@noirlab.edu" in response.content
        assert (
            reverse("user-antares-kafka-login", args=[user.pk]).encode()
            in response.content
        )

    def test_says_starts_not_restarts(self, client, user):
        """"Restarts" is meaningless on a first visit."""
        client.force_login(user)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"Submitting starts the consumer" in response.content
