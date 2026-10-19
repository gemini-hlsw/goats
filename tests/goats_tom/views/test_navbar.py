"""Tests for the navbar's right-hand menus and the footer links."""

import pytest
from django.urls import reverse

from goats_tom.tests.factories import UserFactory


def _page(client) -> str:
    return client.get(reverse("login")).content.decode()


@pytest.mark.django_db
def test_downloads_are_offered_only_when_signed_in(client):
    assert 'id="navbarDownloadLink"' not in _page(client)

    client.force_login(UserFactory())
    assert 'id="navbarDownloadLink"' in _page(client)


@pytest.mark.django_db
def test_github_and_the_documentation_open_in_a_new_tab(client):
    links = [
        'href="https://github.com/gemini-hlsw/goats" target="_blank"',
        'href="https://goats.readthedocs.io/en/latest/index.html" target="_blank"',
    ]

    assert all(link in _page(client) for link in links)

    client.force_login(UserFactory())
    assert all(link in _page(client) for link in links)


@pytest.mark.django_db
def test_the_log_in_link_uses_the_verb(client):
    content = _page(client)

    assert 'title="Log in to GOATS"' in content
    assert '<span class="ms-2">Log in</span>' in content
    assert ">Login<" not in content


@pytest.mark.django_db
def test_shut_down_is_not_offered_when_signed_out(client):
    assert 'id="shutdownBtn"' not in _page(client)


@pytest.mark.django_db
def test_shut_down_is_in_the_user_menu_when_signed_in(client):
    client.force_login(UserFactory())

    content = _page(client)

    assert content.count('id="shutdownBtn"') == 1
    assert '<button id="shutdownBtn" type="button" class="dropdown-item' in content


@pytest.mark.django_db
def test_the_theme_toggle_is_a_navbar_icon_signed_in_or_not(client):
    assert '<button id="colorThemeToggle" class="nav-link' in _page(client)

    client.force_login(UserFactory())
    content = _page(client)

    assert content.count('id="colorThemeToggle"') == 1
    assert '<button id="colorThemeToggle" class="nav-link' in content


@pytest.mark.django_db
def test_the_user_menu_names_the_account_then_lists_its_options(client):
    client.force_login(
        UserFactory(
            is_superuser=True,
            first_name="Grace",
            last_name="Hopper",
            email="grace@example.org",
        )
    )

    content = _page(client)

    order = [
        "Grace Hopper",
        "grace@example.org",
        "Account settings",
        "Service status",
        "Users",
        "Log out",
        "Shut down GOATS",
    ]
    positions = [content.index(label, content.index('id="navbarUserLink"')) for label in order]
    assert positions == sorted(positions)
