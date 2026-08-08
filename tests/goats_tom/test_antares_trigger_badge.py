"""Render tests for the Gemini trigger badge on the locus dashboard.

The badge partial is only exercised at render time, so a template error in it
would reach the dashboard before it reached anyone's attention -- nothing else
in the suite renders `partials/antares_locus_table.html`.
"""

import pytest
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from goats_tom.models import (
    AntaresLocus,
    AntaresStreamSubscription,
    GeminiTriggerRecord,
    GPPLogin,
)

TEMPLATE = "partials/antares_trigger_badge.html"


@pytest.fixture()
def subscription(db):
    """A subscription to hang trigger records off."""
    user = User.objects.create_user("badgepi")
    GPPLogin.objects.create(user=user, token="tok")
    return AntaresStreamSubscription.objects.create(
        owner=user,
        topics=["t"],
        trigger_gemini_observations=True,
        gpp_program_id="p-1",
        gpp_observation_id="o-1",
    )


def _render(trigger, label_class="text-danger", label_text="Failed"):
    return render_to_string(
        TEMPLATE,
        {
            "trigger": trigger,
            "label_class": label_class,
            "label_text": label_text,
        },
    )


@pytest.mark.django_db()
class TestTriggerBadge:
    """The badge reveals its message on click rather than inline."""

    def test_failure_detail_is_present_but_collapsed(self, subscription):
        """In the markup, so it is reachable; hidden, so it is not noise."""
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT1",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="Event loop is closed. Nothing was created in GPP.",
        )
        html = _render(record)

        assert "Nothing was created in GPP." in html
        assert "antares-trigger-detail" in html
        assert 'aria-expanded="false"' in html
        # Hidden by a stylesheet rule keyed on this attribute, not by a class
        # on the row -- the row is replaced on a timer, the stylesheet is not.
        assert 'data-locus-id="ANT1"' in html

    def test_the_badge_is_a_button_that_cannot_submit_the_form(
        self, subscription
    ):
        """It sits inside the save-targets form.

        A button without an explicit type submits its form, which here would
        save every ticked locus the moment someone read a failure message.
        """
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT2",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="boom",
        )
        html = _render(record)

        assert 'type="button"' in html

    def test_the_control_targets_its_own_panel(self, subscription):
        """Every row has one, so the ids must not collide."""
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT3",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="boom",
        )
        html = _render(record)

        assert 'aria-controls="antares-trigger-detail-ANT3"' in html
        assert 'id="antares-trigger-detail-ANT3"' in html

    def test_a_success_links_to_the_observation(self, subscription, db):
        """Nothing to explain on success, so it links instead of unfolding.

        The message used to interpolate the workflow-state object GPP
        returned, filling the column with a Python repr.
        """
        from tom_observations.models import ObservationRecord
        from tom_targets.models import Target

        target = Target.objects.create(
            name="ANT4TGT", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        observation = ObservationRecord.objects.create(
            target=target,
            facility="GEM",
            observation_id="G-2026A-0166-Q-0892",
            parameters={},
        )
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT4",
            status=GeminiTriggerRecord.STATUS_SUCCESS,
            gpp_observation_id="o-new",
            observation_record=observation,
        )
        html = _render(record, label_class="text-success", label_text="Triggered")

        assert f"/observations/{observation.pk}/" in html
        assert "G-2026A-0166-Q-0892" in html
        assert "antares-trigger-toggle" not in html

    def test_no_button_when_there_is_nothing_to_reveal(self, subscription):
        """A control that opens an empty panel is worse than no control."""
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT5",
            status=GeminiTriggerRecord.STATUS_PENDING,
            detail="",
        )
        html = _render(record, label_class="text-secondary", label_text="Pending")

        assert "antares-trigger-toggle" not in html
        assert "Pending" in html

    def test_detail_text_is_escaped(self, subscription):
        """The detail carries an exception message straight from GPP."""
        record = GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT6",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="<script>alert(1)</script>",
        )
        html = _render(record)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html


@pytest.mark.django_db()
class TestDashboardTableRendersTheBadge:
    """End to end, through the view the dashboard actually polls.

    The partial tests above render the badge in isolation, which would still
    pass if the include in `partials/antares_locus_table.html` were wrong.
    Nothing else in the suite renders that table.
    """

    def test_the_table_renders_a_collapsed_failure(self, subscription, client):
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT9",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a1",
        )
        GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id="ANT9",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="Event loop is closed. Nothing was created in GPP.",
        )
        client.force_login(subscription.owner)

        response = client.get("/antares/loci/table/")
        body = response.content.decode()

        assert response.status_code == 200
        assert "antares-trigger-toggle" in body
        assert "antares-trigger-detail-ANT9" in body
        assert "Nothing was created in GPP." in body


class TestToggleDoesNotFeedTheObserver:
    """Guards the loop that hung the dashboard.

    The dashboard watches the table with a `MutationObserver` configured for
    ``childList`` on the whole subtree. An earlier version of the toggle
    flipped a caret glyph with `innerHTML`, which is a childList change inside
    that subtree: expanding a badge retriggered the observer, which reapplied
    the open state, which rewrote the glyph, without end. One expanded row was
    enough to lock the page up.

    Read as text rather than executed -- there is no JS runtime in the test
    environment -- so this catches the reintroduction of the pattern, not
    every possible variant of it.
    """

    def _script(self):
        from pathlib import Path

        from django.conf import settings

        for directory in settings.TEMPLATES[0]["DIRS"] or []:
            candidate = Path(directory) / "antares_locus_dashboard.html"
            if candidate.exists():
                return candidate.read_text()
        import goats_tom

        return (
            Path(goats_tom.__file__).parent
            / "templates"
            / "antares_locus_dashboard.html"
        ).read_text()

    def test_the_toggle_writes_no_markup_into_the_table(self):
        """`setTriggerDetail` must not touch the observed subtree.

        It may write to the out-of-table stylesheet -- that element is not
        observed -- but nothing inside the table.
        """
        script = self._script()
        start = script.index("function setTriggerDetail")
        body = script[start : script.index("function applyTriggerAria")]

        assert "innerHTML" not in body
        assert "appendChild" not in body
        # The only write is to the stylesheet, via writeTriggerOpenRules.
        assert "writeTriggerOpenRules" in body

    def test_only_the_stylesheet_is_written_as_text(self):
        """`textContent` is assigned to the <style> element and nothing else."""
        script = self._script()
        start = script.index("function writeTriggerOpenRules")
        body = script[start : script.index("function setTriggerDetail")]

        assert "sheet.textContent" in body

    def test_the_caret_glyph_is_never_rewritten(self):
        """The chevron turns with a CSS transform, not a new glyph."""
        script = self._script()

        assert "antares-trigger-caret" not in script
        assert "rotate(90deg)" in script

    def test_open_state_lives_outside_the_swapped_table(self):
        """The reason an open message survives the 15s refresh.

        The table is replaced wholesale every 15s and partly rewritten every
        3s by the saved-status poll, so open state written onto a row is
        destroyed on a timer. Rules in a stylesheet outside the table apply to
        whatever markup exists, including markup that arrives later.
        """
        script = self._script()

        assert 'id="antares-trigger-open-rules"' in script
        assert "writeTriggerOpenRules" in script
        # The <style> element must sit outside the observed container.
        assert script.index('id="antares-trigger-open-rules"') < script.index(
            "MutationObserver"
        )

    def test_locus_ids_are_validated_before_reaching_the_stylesheet(self):
        """They are interpolated into a selector, so they are refused, not escaped."""
        assert "SAFE_LOCUS_ID" in self._script()


@pytest.mark.django_db()
class TestSavedBadgeLinksToTheTarget:
    """The badge names something the PI will want to open."""

    def test_it_links_when_the_target_is_resolvable(self, subscription, client):
        from tom_targets.models import Target

        from goats_tom.models import AntaresLocus, AntaresTargetSave

        target = Target.objects.create(
            name="ANTLINK", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANTLINK",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a1",
        )
        AntaresTargetSave.objects.create(
            locus_id="ANTLINK", saved_by=subscription.owner
        )
        client.force_login(subscription.owner)

        body = client.get("/antares/loci/table/").content.decode()

        assert target.get_absolute_url() in body

    def test_an_unsaved_locus_has_no_link(self, subscription, client):
        from goats_tom.models import AntaresLocus

        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANTPLAIN",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a1",
        )
        client.force_login(subscription.owner)

        body = client.get("/antares/loci/table/").content.decode()

        assert "&#10003; Saved" not in body


class TestTemplateCommentsDoNotLeak:
    """Django's `{# #}` comment does not span lines.

    A multi-line one is not recognised as a comment at all: its text renders
    verbatim onto the page, and if it happens to contain a template tag, that
    tag is parsed and can raise. Both happened while building this column.
    """

    def _antares_templates(self):
        from pathlib import Path

        import goats_tom

        root = Path(goats_tom.__file__).parent / "templates"
        return [
            path
            for path in root.rglob("*antares*.html")
        ]

    def test_no_multi_line_hash_comments(self):
        import re

        offenders = []
        for path in self._antares_templates():
            for match in re.finditer(r"\{#", path.read_text()):
                line = path.read_text()[match.start() :].split("\n", 1)[0]
                if "#}" not in line:
                    offenders.append(f"{path.name}: {line.strip()[:60]}")

        assert not offenders, (
            "multi-line {# #} renders as visible text; use "
            f"{{% comment %}} instead: {offenders}"
        )
