"""Tests for GPP_ENV driving both the ODB and the Explore URL."""

import re
from pathlib import Path

import pytest
from django.test import override_settings

TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src" / "goats_cli" / "goats_template" / "{{ project_name }}" / "settings"
)


def _loader_source() -> str:
    return (TEMPLATE_ROOT / "__init__.py.jinja").read_text()


class TestEnvironmentDerivation:
    """The GPP environment comes from the installed package, nothing else."""

    def test_derived_from_the_installed_package(self):
        """`gpp-client` fixes its environment at build time.

        `GPPClient.__init__` takes only a token; the ODB URL and which token
        field to read both come from a constant baked into the package. So the
        environment is a property of which build is installed, and there is
        nothing for a Django setting to decide.
        """
        source = _loader_source()
        assert "_get_packaged_environment" in source

    def test_no_environment_override_is_exported(self):
        """Exporting GPP_ENVIRONMENT_OVERRIDE was wrong and is gone.

        Regression test: the override only half-applies inside the library --
        it moves the URL but not where an explicitly-passed token is stored --
        so it raised "A token is required for the development environment"
        and could never have worked.
        """
        source = _loader_source()
        assert 'setdefault("GPP_ENVIRONMENT_OVERRIDE"' not in source
        assert "_os.environ" not in source

    def test_gpp_env_is_not_settable_anywhere(self):
        """One source, so nothing can fall out of step with the package."""
        settings_dir = TEMPLATE_ROOT
        offenders = []
        for path in settings_dir.rglob("*.jinja"):
            if path.name == "__init__.py.jinja":
                continue
            for line in path.read_text().splitlines():
                if re.match(r"\s*GPP_ENV\s*=", line):
                    offenders.append(f"{path.name}: {line.strip()}")
        assert not offenders, offenders

    def test_missing_client_does_not_break_settings(self):
        """A broken gpp-client must not stop GOATS from starting."""
        source = _loader_source()
        assert "except Exception" in source
        assert '"UNKNOWN"' in source

    def test_development_maps_to_the_dev_explore(self):
        source = _loader_source()
        block = source[source.index("GPP_EXPLORE_URL") :]
        block = block[: block.index(")") + 1]
        assert "explore-dev.lucuma.xyz" in block
        assert 'if GPP_ENV == "DEVELOPMENT"' in block


class TestNoHardcodedExploreUrls:
    """Nothing should link to a fixed environment any more."""

    def test_observation_detail_uses_the_setting(self):
        """The per-observation link follows GPP_ENV too.

        An observation submitted to the development ODB has no page in
        production Explore, so a fixed link would 404 for exactly the
        observations GOATS created.
        """
        view = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "views" / "observation_record_detail.py"
        ).read_text()
        assert "settings.GPP_EXPLORE_URL" in view
        assert "https://explore.gemini.edu" not in view

    def test_navbar_uses_the_context_variable(self):
        navbar = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "templates" / "navbar.html"
        ).read_text()
        assert "{{ gpp_explore_url }}" in navbar
        assert "https://explore.gemini.edu" not in navbar


@pytest.mark.django_db()
class TestExploreUrlInTemplates:
    """The context processor reaches rendered pages."""

    def test_navbar_renders_the_configured_url(self, client):
        from django.contrib.auth.models import User
        from django.urls import reverse

        user = User.objects.create_user("explorer", password="pw-long-enough-1")
        client.force_login(user)
        with override_settings(GPP_EXPLORE_URL="https://explore-dev.lucuma.xyz"):
            content = client.get(reverse("home")).content
        assert b"https://explore-dev.lucuma.xyz" in content

    def test_processor_falls_back_when_unset(self):
        """An older instance without the setting must not break rendering."""
        from goats_tom.context_processors import gpp_explore_processor

        with override_settings():
            from django.conf import settings

            del settings.GPP_EXPLORE_URL
            result = gpp_explore_processor(None)
        assert result["gpp_explore_url"] == "https://explore.gemini.edu"
