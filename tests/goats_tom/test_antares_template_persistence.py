"""Tests that an applied observing template survives editing the ingestion page.

The template is the part of the configuration a PI cannot reconstruct from
memory -- it carries the source profile and instrument that automatic
triggering depends on -- and it is held in hidden fields rather than typed. So
every path that re-renders the page has to put it back.
"""

import pytest
from django.contrib.auth.models import User

from goats_tom.forms import AntaresStreamSubscribeForm
from goats_tom.models import AntaresStreamSubscription


def _applied_template_kwargs():
    return {
        "gpp_program_id": "p-1",
        "gpp_observation_id": "o-1",
        "gpp_target_id": "t-1",
        "gpp_instrument": "GMOS_NORTH",
        "gpp_workflow_state": "READY",
        "gpp_observation_overrides": {"subtitle": "x"},
        "gpp_target_overrides": {"existence": "PRESENT"},
    }


@pytest.fixture()
def owner(db):
    return User.objects.create_user("tmplpi", password="x")


@pytest.mark.django_db()
class TestTemplateSurvivesReRendering:
    """Both re-render paths restore the hidden template fields."""

    def _initial(self, owner, client, **extra):
        AntaresStreamSubscription.objects.create(
            owner=owner,
            topics=["t"],
            trigger_gemini_observations=True,
            save_all_targets=True,
            **_applied_template_kwargs(),
            **extra,
        )
        client.force_login(owner)
        response = client.get("/antares/stream/subscribe/")
        return response

    def test_a_normal_edit_keeps_the_template(self, owner, client):
        response = self._initial(owner, client)
        body = response.content.decode()

        assert response.status_code == 200
        assert 'value="t-1"' in body
        assert "GMOS_NORTH" in body

    def test_a_draft_re_render_keeps_the_template(self, owner, client):
        """The path taken after a failed submission.

        It restored only the typed fields, so the hidden template fields came
        back empty and the next submit posted a blank template. With triggering
        on that fails validation, saves another draft, and drops it again --
        a loop with nothing on screen explaining it.
        """
        response = self._initial(
            owner,
            client,
            draft_topics="other",
            draft_error="handler failed to compile",
            draft_trigger_gemini_observations=True,
        )
        body = response.content.decode()

        assert response.status_code == 200
        assert 'value="t-1"' in body, "draft re-render dropped the target id"
        assert "GMOS_NORTH" in body, "draft re-render dropped the instrument"

    def test_the_page_renders_with_target_overrides_stored(
        self, owner, client
    ):
        """Guards an `UnboundLocalError`.

        `json.dumps` was called above a function-local `import json`, so any
        subscription with stored target overrides raised on page load. No test
        opened the page in that state, so nothing caught it.
        """
        response = self._initial(owner, client)

        assert response.status_code == 200
        assert "existence" in response.content.decode()


class TestAppliedTemplateIsRequired:
    """Selecting a template is not the same as applying it."""

    def _form(self, **overrides):
        data = {
            "topics": "t",
            "trigger_gemini_observations": "on",
            "save_all_targets": "on",
            "gpp_program_id": "p-1",
            "gpp_observation_id": "o-1",
        }
        data.update(overrides)
        return AntaresStreamSubscribeForm(data=data, user=None)

    def test_rejected_with_a_selected_but_unapplied_template(self):
        """Half-configured used to pass and then degrade silently.

        No target id meant a bare target with no source profile; no instrument
        meant the observation was never recorded in GOATS. Neither said so.
        """
        form = self._form()

        assert not form.is_valid()
        assert "trigger_gemini_observations" in form.errors

    def test_rejected_without_an_instrument(self):
        form = self._form(gpp_target_id="t-1")

        assert not form.is_valid()

    def test_rejected_without_a_target(self):
        form = self._form(gpp_instrument="GMOS_NORTH")

        assert not form.is_valid()

    def test_accepted_once_applied(self):
        form = self._form(gpp_target_id="t-1", gpp_instrument="GMOS_NORTH")

        assert form.is_valid(), form.errors

    def test_not_required_when_triggering_is_off(self):
        """The template is only needed by triggering."""
        form = AntaresStreamSubscribeForm(
            data={"topics": "t", "save_all_targets": "on"}, user=None
        )

        assert form.is_valid(), form.errors


class TestServerReadsTemplateIdentifiers:
    """The Apply endpoint takes the target and instrument from the picker."""

    def _source(self):
        from pathlib import Path

        import goats_tom

        return (
            Path(goats_tom.__file__).parent / "api_views" / "gpp" / "observations.py"
        ).read_text()

    def test_context_serializer_is_not_used_for_them(self):
        """It requires a GOATS target primary key, which this page has none of.

        Routed through it, both identifiers came back empty on every Apply and
        the ingestion button stayed disabled with a template visibly applied.
        """
        source = self._source()
        start = source.index("def serialize_template_overrides")
        body = source[start : source.index("url_path=\"create-and-save\"")]

        assert "templateTargetId" in body
        assert "templateInstrument" in body
        assert "context_serializer" not in body

    def test_the_observing_mode_is_validated(self):
        """It arrives from the browser, so it is checked against the enum."""
        source = self._source()
        start = source.index("def serialize_template_overrides")
        body = source[start : source.index("url_path=\"create-and-save\"")]

        assert "ObservingModeType" in body
        assert "valid_modes" in body
