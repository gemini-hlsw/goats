"""Tests for automatic Gemini triggering guards.

These use mocks throughout: there is no GPP endpoint available in the test
environment. The guards are the part that protects a real telescope
allocation, so they are tested exhaustively here -- but the GPP calls
themselves still need validating against a real test programme before this is
trusted with a live allocation.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from goats_tom.gemini_trigger import trigger_gemini_observation
from goats_tom.models import (
    AntaresStreamSubscription,
    GeminiTriggerRecord,
    GPPLogin,
)
from tom_targets.models import Target


@pytest.fixture()
def owner(db):
    """A PI with GPP credentials stored."""
    user = User.objects.create_user("triggerpi")
    GPPLogin.objects.create(user=user, token="tok")
    return user


@pytest.fixture()
def subscription(owner):
    """A subscription configured to trigger, with a template."""
    return AntaresStreamSubscription.objects.create(
        owner=owner,
        topics=["t"],
        trigger_gemini_observations=True,
        gpp_program_id="p-1",
        gpp_observation_id="o-1",
        max_triggers=10,
    )


@pytest.fixture()
def target(db):
    """A saved target to point the observation at."""
    return Target.objects.create(
        name="ANT2026abc", type=Target.SIDEREAL, ra=10.0, dec=20.0
    )


def _snapshot(allocated=10.0, charged=0.0, band="BAND1"):
    """Patch the band time accounting with given hours."""
    return patch(
        "goats_tom.gemini_trigger._fetch_band_time",
        return_value=(band, allocated, charged),
    )


def _clone_ok():
    """Patch the clone step to succeed."""
    return patch(
        "goats_tom.gpp_observation_builder.clone_observation_for_target",
        return_value={"target_id": "t-new", "observation_id": "o-new"},
    )


@pytest.mark.django_db()
class TestHappyPath:
    """A permitted trigger creates an observation and records it."""

    def test_success_records_ids(self, subscription, target):
        with _snapshot(), _clone_ok(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS
        assert record.gpp_observation_id == "o-new"
        assert record.gpp_target_id == "t-new"

    def test_no_execution_time_is_recorded(self, subscription, target):
        """GPP provides no cost for an unexecuted observation.

        The field is kept on the model rather than migrated away, in case a
        cost becomes available later, but nothing populates it now -- storing
        a made-up number would be worse than storing none.
        """
        with _snapshot(), _clone_ok(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.execution_time_hours is None


@pytest.mark.django_db()
class TestIdempotency:
    """The same locus must never be triggered twice."""

    def test_second_attempt_is_refused(self, subscription, target):
        """The reserved row is what makes a duplicate impossible.

        A duplicate would create a second observation on the same target and
        charge the allocation twice -- the worst outcome available here.
        """
        with _snapshot(), _clone_ok(), patch("gpp_client.GPPClient"):
            trigger_gemini_observation(subscription, target.name, target)
            second = trigger_gemini_observation(subscription, target.name, target)
        assert second is None
        assert GeminiTriggerRecord.objects.filter(locus_id=target.name).count() == 1

    def test_no_clone_on_second_attempt(self, subscription, target):
        """It stops before GPP is contacted, not after."""
        with _snapshot(), patch("gpp_client.GPPClient"):
            with _clone_ok() as clone:
                trigger_gemini_observation(subscription, target.name, target)
                assert clone.call_count == 1
                trigger_gemini_observation(subscription, target.name, target)
                assert clone.call_count == 1

    def test_failed_record_blocks_retry(self, subscription, target):
        """A failure may have created an observation despite the error.

        Retrying would risk a second one, so it is left for a human.
        """
        GeminiTriggerRecord.objects.create(
            subscription=subscription,
            locus_id=target.name,
            status=GeminiTriggerRecord.STATUS_FAILED,
        )
        with _snapshot(), patch("gpp_client.GPPClient"):
            with _clone_ok() as clone:
                result = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert result is None
        clone.assert_not_called()


@pytest.mark.django_db()
class TestTriggerCap:
    """The lifetime cap stops triggering without stopping ingestion."""

    def test_refuses_at_the_cap(self, subscription, target):
        subscription.max_triggers = 2
        subscription.save()
        for i in range(2):
            GeminiTriggerRecord.objects.create(
                subscription=subscription,
                locus_id=f"OLD{i}",
                status=GeminiTriggerRecord.STATUS_SUCCESS,
            )
        with _snapshot(), patch("gpp_client.GPPClient"):
            with _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "limit reached" in record.detail.lower()
        clone.assert_not_called()

    def test_blank_cap_means_unlimited(self, subscription, target):
        subscription.max_triggers = None
        subscription.save()
        for i in range(50):
            GeminiTriggerRecord.objects.create(
                subscription=subscription,
                locus_id=f"OLD{i}",
                status=GeminiTriggerRecord.STATUS_SUCCESS,
            )
        with _snapshot(), _clone_ok(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS

    def test_skipped_attempts_do_not_consume_the_cap(self, subscription, target):
        """Otherwise a refusal spends the budget it was protecting."""
        subscription.max_triggers = 2
        subscription.save()
        for i in range(5):
            GeminiTriggerRecord.objects.create(
                subscription=subscription,
                locus_id=f"SKIP{i}",
                status=GeminiTriggerRecord.STATUS_SKIPPED,
            )
        with _snapshot(), _clone_ok(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS

    def test_failed_attempts_do_consume_the_cap(self, subscription, target):
        """A failure may have created an observation, so it is not free."""
        subscription.max_triggers = 2
        subscription.save()
        for i in range(2):
            GeminiTriggerRecord.objects.create(
                subscription=subscription,
                locus_id=f"FAIL{i}",
                status=GeminiTriggerRecord.STATUS_FAILED,
            )
        with _snapshot(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED


@pytest.mark.django_db()
class TestBandTimeGuard:
    """Triggering stops when the template's science band is exhausted."""

    def test_refuses_when_the_band_is_used_up(self, subscription, target):
        with _snapshot(allocated=10.0, charged=10.0):
            with patch("gpp_client.GPPClient"), _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "no time left" in record.detail.lower()
        clone.assert_not_called()

    def test_allows_while_time_remains(self, subscription, target):
        """No per-observation cost is knowable, so any remaining time passes.

        GPP does not compute a cost for an unexecuted observation -- an
        earlier version demanded one and refused without it, which could never
        succeed. The trigger cap bounds how far past a nearly-exhausted band
        this can go.
        """
        with _snapshot(allocated=10.0, charged=9.99):
            with patch("gpp_client.GPPClient"), _clone_ok():
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS

    def test_refuses_when_no_time_is_granted(self, subscription, target):
        """No allocation in the band means there is nothing to spend.

        Regression test: this was allowed through on the grounds that zero
        might mean "not recorded". Reading an ambiguous value permissively is
        only safe when being wrong is cheap, and this consumes real telescope
        time.
        """
        with _snapshot(allocated=0.0, charged=0.0):
            with patch("gpp_client.GPPClient"), _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "no time granted" in record.detail.lower()
        clone.assert_not_called()

    def test_unreachable_gpp_refuses_rather_than_guesses(
        self, subscription, target
    ):
        """Triggering blind would defeat the guard entirely."""
        from goats_tom.gemini_trigger import TriggerFailed

        with patch(
            "goats_tom.gemini_trigger._fetch_band_time",
            side_effect=TriggerFailed("GPP unreachable"),
        ):
            with patch("gpp_client.GPPClient"), _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_FAILED
        clone.assert_not_called()

    def test_no_execution_time_is_required(self):
        """Regression test: this made every trigger fail.

        The check demanded an execution time for the template and refused
        without one. GPP never provides it -- the field is not even returned
        by the observations query -- so the guard could only ever refuse.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "gemini_trigger.py"
        ).read_text()
        assert "_execution_hours" not in source
        assert "did not report an execution time" not in source


@pytest.mark.django_db()
class TestConfigurationGuards:
    """Misconfiguration is reported, not silently ignored."""

    def test_no_credentials(self, db, target):
        user = User.objects.create_user("nogpp")
        subscription = AntaresStreamSubscription.objects.create(
            owner=user,
            topics=["t"],
            trigger_gemini_observations=True,
            gpp_program_id="p-1",
            gpp_observation_id="o-1",
        )
        record = trigger_gemini_observation(subscription, target.name, target)
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "credentials" in record.detail.lower()

    def test_no_template_configured(self, owner, target):
        subscription = AntaresStreamSubscription.objects.create(
            owner=owner, topics=["t"], trigger_gemini_observations=True
        )
        record = trigger_gemini_observation(subscription, target.name, target)
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "template" in record.detail.lower()


@pytest.mark.django_db()
class TestCloneFailure:
    """A failure after the clone began is recorded, never retried."""

    def test_records_failure_with_a_warning(self, subscription, target):
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                side_effect=RuntimeError("boom"),
            ):
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_FAILED
        # The PI must know the observation might exist regardless.
        assert "explore" in record.detail.lower()


@pytest.mark.django_db()
class TestFormRequiresTemplate:
    """Enabling triggering without a template is rejected up front."""

    def test_rejected_without_template(self):
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "trigger_gemini_observations": "on",
                "save_all_targets": "on",
            },
            user=None,
        )
        assert not form.is_valid()
        assert "trigger_gemini_observations" in form.errors

    def test_auto_save_is_implied_not_required(self):
        """Ticking triggering turns auto-save on rather than refusing.

        Triggering needs a target to point the observation at, so the two are
        not really a choice -- rejecting the submission was pedantry. The
        browser ticks the box too, so the change is visible.
        """
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "trigger_gemini_observations": "on",
                "gpp_program_id": "p-1",
                "gpp_observation_id": "o-1",
            },
            user=None,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["save_all_targets"] is True

    def test_accepted_with_template_and_auto_save(self):
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {
                "topics": "sometopic",
                "trigger_gemini_observations": "on",
                "save_all_targets": "on",
                "gpp_program_id": "p-1",
                "gpp_observation_id": "o-1",
            },
            user=None,
        )
        assert form.is_valid(), form.errors

    def test_auto_save_alone_is_fine(self):
        """The dependency is one-way: saving without triggering is normal."""
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {"topics": "sometopic", "save_all_targets": "on"}, user=None
        )
        assert form.is_valid(), form.errors


@pytest.mark.django_db()
class TestTriggerHelpText:
    """The checkbox states its prerequisites."""

    def test_links_to_gpp_credentials(self, owner):
        """A user without credentials needs to know where to store them.

        The text previously read "Not yet active; checking this currently has
        no effect", which was true when the feature was a placeholder and is
        now actively misleading.
        """
        from goats_tom.forms import AntaresStreamSubscribeForm

        help_text = AntaresStreamSubscribeForm(user=owner).fields[
            "trigger_gemini_observations"
        ].help_text
        assert f"/users/{owner.pk}/gpp/" in help_text or "gpp" in help_text.lower()
        assert "auto-saving" in help_text

    def test_no_broken_link_without_a_user(self):
        """The form is also built unbound in tests and dry runs."""
        from goats_tom.forms import AntaresStreamSubscribeForm

        help_text = AntaresStreamSubscribeForm(user=None).fields[
            "trigger_gemini_observations"
        ].help_text
        assert "<a href" not in help_text
        assert "GPP credentials" in help_text

    def test_help_says_auto_saving_targets(self):
        """"auto-saving above" was ambiguous about what is saved."""
        from goats_tom.forms import AntaresStreamSubscribeForm

        help_text = AntaresStreamSubscribeForm(user=None).fields[
            "trigger_gemini_observations"
        ].help_text
        assert "auto-saving targets above" in help_text

    def test_cap_input_is_not_full_width(self):
        """A two-digit field should not span the page."""
        from goats_tom.forms import AntaresStreamSubscribeForm

        widget = AntaresStreamSubscribeForm(user=None).fields[
            "max_triggers"
        ].widget
        assert "max-width" in widget.attrs.get("style", "")

    def test_cap_help_drops_nightly_wording(self):
        """The cap is a lifetime total; "not per night" invited confusion."""
        from goats_tom.forms import AntaresStreamSubscribeForm

        help_text = AntaresStreamSubscribeForm(user=None).fields[
            "max_triggers"
        ].help_text
        assert "per night" not in help_text
        assert "Total for this subscription" in help_text


@pytest.mark.django_db()
class TestTemplatePickerMount:
    """The picker is present but only built when triggering is enabled."""

    def test_offcanvas_and_dependencies_are_loaded(self, client, owner):
        """The panel embeds ObservationForm, which has its own dependencies.

        Missing one fails only at runtime with a bare "X is not defined", so
        the set is pinned here.
        """
        from django.urls import reverse

        client.force_login(owner)
        content = client.get(reverse("antares-stream-subscribe")).content
        for script in (
            b"observation_form.js",
            b"fields.js",
            b"exposure_mode_editor.js",
            b"scheduling_windows_editor.js",
        ):
            assert script in content, script

    def test_all_observation_form_dependencies_are_loaded(self):
        """Every script the observation page loads for the form is loaded here.

        Regression test: `js/utils.js` was missing, so every editor's
        `Utils.createElement` call threw and the panel reported "could not
        load this observation's parameters" -- which read like a data problem
        rather than a broken page.

        Compared against the observation page rather than a fixed list, so a
        dependency added there cannot silently break this panel.
        """
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src" / "goats_tom" / "templates"
        grab = lambda text: set(
            re.findall(r"static '(js/[^']+)'", text)
        )
        observation_page = grab(
            (root / "tom_observations" / "observation_form.html").read_text()
        )
        ingestion_page = grab((root / "antares_stream_subscribe.html").read_text())

        # These drive the observation page itself, not ObservationForm.
        page_only = {
            "js/gpp/gpp.js",
            "js/gpp/app.js",
            "js/gpp/program_observations_panel.js",
        }
        missing = (observation_page - ingestion_page) - page_only
        assert not missing, f"missing script dependencies: {sorted(missing)}"

    def test_editor_uses_too_mode(self):
        """The form filters fields by mode, so "normal" shows the wrong set."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()
        assert 'mode: "too"' in source

    def test_picker_renders_an_offcanvas(self):
        """The panel is a Bootstrap offcanvas, matching the DRAGONS help panel.

        Asserted against the source rather than a response: the markup is
        built by the picker at runtime, so it never appears server-side.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "goats_tom"
            / "static"
            / "js"
            / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "offcanvas offcanvas-end" in source
        assert 'id="gppTemplateOffcanvas"' in source
        # Backdrop off so the subscription form stays usable behind it.
        assert 'data-bs-backdrop="false"' in source

    def test_only_too_observations_are_offered(self):
        """Automatic triggering responds to transients, which is what ToO is.

        Cloning an ordinary scheduled observation would repeat something the
        programme never intended to be run per alert.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "groups.normal" not in source
        assert "Other observations" not in source
        assert "target-of-opportunity" in source.lower()

    def test_editor_uses_cached_list_data(self):
        """The detail endpoint is a placeholder returning a thinner shape.

        Regression test: fetching it produced "could not load this
        observation's parameters", because ObservationForm cannot render that
        shape. The list response already carries everything the editor needs,
        which is why the observation page caches it rather than re-fetching.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "#observations.get(observationId)" in source
        assert "gpp/observations/${encodeURIComponent(observationId)}/" not in source

    def test_labels_match_the_agreed_wording(self):
        """Programmes and configurations are named consistently."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "Active Programs" in source
        assert "Approved ToO Configurations" in source

    def test_edits_never_write_to_gpp(self):
        """The template belongs to a real programme and must stay untouched."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "serialize-overrides" in source
        assert "update-template" not in source
        assert "update-only" not in source

    def test_picker_saves_without_touching_the_target(self):
        """Template edits must not alter the template's own target.

        The target is replaced on every clone, so editing it would change a
        real object that is not the one being observed.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "goats_tom"
            / "static"
            / "js"
            / "gpp"
            / "template_picker.js"
        ).read_text()
        assert "gpp/observations/serialize-overrides/" in source

    def test_picker_script_is_loaded(self, client, owner):
        from django.urls import reverse

        client.force_login(owner)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b"template_picker.js" in response.content

    def test_hidden_inputs_exist_for_the_picker(self, client, owner):
        """The picker writes the chosen ids into these."""
        from django.urls import reverse

        client.force_login(owner)
        response = client.get(reverse("antares-stream-subscribe"))
        assert b'id="id_gpp_program_id"' in response.content
        assert b'id="id_gpp_observation_id"' in response.content


@pytest.mark.django_db()
class TestTemplateOverrides:
    """Overrides apply to the clone, never to the template."""

    def test_overrides_reach_the_clone(self, subscription, target):
        subscription.gpp_observation_overrides = {"posAngleConstraint": {"mode": "FIXED"}}
        subscription.save()
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["overrides"] == {
            "posAngleConstraint": {"mode": "FIXED"}
        }

    def test_empty_overrides_pass_none(self, subscription, target):
        """An empty dict must not be sent as an override set."""
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["overrides"] is None

    def test_target_environment_cannot_be_overridden(self):
        """Pointing the clone at the new locus is the whole purpose.

        A stale target_environment left in a stored override would silently
        observe the wrong object.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "gpp_observation_builder.py"
        ).read_text()
        assert 'properties_kwargs.pop("targetEnvironment", None)' in source

    def test_form_rejects_malformed_overrides(self):
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {
                "topics": "t",
                "gpp_observation_overrides": "not json",
            },
            user=None,
        )
        assert not form.is_valid()
        assert "gpp_observation_overrides" in form.errors

    def test_form_accepts_empty_overrides(self):
        from goats_tom.forms import AntaresStreamSubscribeForm

        form = AntaresStreamSubscribeForm(
            {"topics": "t", "gpp_observation_overrides": ""}, user=None
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["gpp_observation_overrides"] == {}


@pytest.mark.django_db()
class TestObserverNotesLink:
    """The ANTARES page is substituted per locus, never appended."""

    def test_token_is_replaced(self):
        from goats_tom.gemini_trigger import _apply_locus_url

        result = _apply_locus_url(
            {"observerNotes": "ANTARES locus: {locus_url}"}, "ANT2026abc"
        )
        assert "ANT2026abc" in result["observerNotes"]
        assert "{locus_url}" not in result["observerNotes"]

    def test_omission_is_respected(self):
        """A PI who removed the token gets no link.

        Silently appending a URL to notes somebody deliberately edited would
        be surprising, so substitution is the only mechanism.
        """
        from goats_tom.gemini_trigger import _apply_locus_url

        result = _apply_locus_url({"observerNotes": "My own notes"}, "ANT1")
        assert result["observerNotes"] == "My own notes"
        assert "antares" not in result["observerNotes"].lower()

    def test_absent_notes_are_left_alone(self):
        from goats_tom.gemini_trigger import _apply_locus_url

        assert _apply_locus_url({}, "ANT1") == {}

    def test_stored_overrides_keep_the_token(self):
        """Substitution must not consume the token.

        The stored value is reused for every locus, so replacing it in place
        would mean only the first trigger got a link.
        """
        from goats_tom.gemini_trigger import _apply_locus_url

        stored = {"observerNotes": "See {locus_url}"}
        _apply_locus_url(stored, "ANT1")
        assert stored["observerNotes"] == "See {locus_url}"

    def test_url_follows_the_configured_environment(self):
        """A development deployment should not link to production."""
        from goats_tom.gemini_trigger import _locus_url

        url = _locus_url("ANT2026abc")
        assert url.endswith("/loci/ANT2026abc")
        assert "antares" in url

    def test_trigger_substitutes_before_cloning(self, subscription, target):
        """The clone receives the resolved link, not the token."""
        subscription.gpp_observation_overrides = {
            "observerNotes": "ANTARES locus: {locus_url}"
        }
        subscription.save()
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        notes = clone.call_args.kwargs["overrides"]["observerNotes"]
        assert target.name in notes
        assert "{locus_url}" not in notes


class TestTemplateEditorSections:
    """Sections without meaning for a template are omitted."""

    def _picker_source(self):
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()

    def test_finder_charts_are_hidden(self):
        """They are prepared per target, and there is no target yet."""
        assert 'hideSections: ["Finder Charts"]' in self._picker_source()

    def test_observer_notes_are_seeded(self):
        assert "{locus_url}" in self._picker_source()

    def test_observer_notes_selector_matches_the_real_dom_id(self):
        """ObservationForm builds ids as `${id}${CapitalizedElement}`.

        Regression test: the picker queried the bare "observerNotes" id, which
        matched nothing, so the field rendered blank with no error -- the token
        and its placeholder were silently dropped.
        """
        source = self._picker_source()
        assert "observerNotesTextarea" in source

    def test_field_id_convention_still_holds(self):
        """Pins the convention the selector above depends on."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "observation_form.js"
        ).read_text()
        assert (
            "`${id}${Utils.capitalizeFirstLetter(element)}`" in source
        ), "field id convention changed; the picker's selector needs updating"

    def test_substitution_key_matches_the_serializer(self):
        """`_apply_locus_url` reads overrides["observerNotes"].

        The form posts `observerNotesTextarea`; the serializer renames it to
        `observerNotes`, which is also GPP's own alias. A mismatch here would
        mean the token was stored but never substituted.
        """
        from pathlib import Path

        serializer_source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "serializers" / "gpp" / "observation.py"
        ).read_text()
        assert 'result["observerNotes"] = observer_notes' in serializer_source

        from gpp_client.generated.input_types import ObservationPropertiesInput

        assert (
            ObservationPropertiesInput.model_fields["observer_notes"].alias
            == "observerNotes"
        )

    def test_help_text_is_the_short_form(self):
        source = self._picker_source()
        assert "Applied to the observations GOATS creates." in source
        assert "The template in GPP is not" not in source

    def test_hidden_sections_do_not_break_get_data(self):
        """Every section-owned editor must be optional in getData().

        Regression test: hiding Finder Charts removed the editor, and
        getData() dereferenced it unconditionally -- "can't access property
        getPendingChanges" surfaced as a failed save with no visible link to
        the hidden section. Both editors are checked, not just the one that
        broke, so the next use of hideSections does not hit the same crash.
        """
        import re
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "observation_form.js"
        ).read_text()
        get_data = source[source.index("  getData()") :]

        editors = re.findall(r"^\s+#(\w*Editor);", source, re.M)
        assert editors, "no editor fields found; this test needs updating"

        for editor in editors:
            unguarded = re.search(
                rf"(?<!\? )this\.#{editor}\.", get_data
            )
            assert not unguarded, (
                f"{editor} is dereferenced unguarded in getData(); hiding its "
                f"section would crash"
            )

    def test_hide_sections_defaults_to_nothing(self):
        """Existing callers must be unaffected by the new option."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "observation_form.js"
        ).read_text()
        assert "hideSections = []" in source
        # A hidden section must drop its fields too, not just its heading.
        assert "#skippingSection" in source


class TestPassbandMapping:
    """ANTARES letters map to GPP's Sloan band names."""

    @pytest.mark.parametrize(
        ("antares", "expected"),
        [
            ("u", "SLOAN_U"),
            ("g", "SLOAN_G"),
            ("r", "SLOAN_R"),
            ("i", "SLOAN_I"),
            ("z", "SLOAN_Z"),
            ("G", "SLOAN_G"),
            ("R", "SLOAN_R"),
            (" g ", "SLOAN_G"),
        ],
    )
    def test_case_insensitive_mapping(self, antares, expected):
        """Surveys are inconsistent about case, so both must work."""
        from goats_tom.gpp_observation_builder import build_source_profile

        profile = build_source_profile(18.4, antares)
        assert profile.point.band_normalized.brightnesses[0].band.value == expected

    def test_magnitude_and_units(self):
        from goats_tom.gpp_observation_builder import build_source_profile

        brightness = build_source_profile(
            19.25, "r"
        ).point.band_normalized.brightnesses[0]
        assert brightness.value == 19.25
        # ANTARES reports AB magnitudes.
        assert brightness.units.value == "AB_MAGNITUDE"

    @pytest.mark.parametrize(
        ("magnitude", "passband"),
        [(None, "g"), (18.4, ""), (18.4, None), (18.4, "w"), (None, None)],
    )
    def test_incomplete_input_yields_no_override(self, magnitude, passband):
        """A partial or unmappable brightness must not be substituted.

        Brightness describes a real object on a real observation, so a guessed
        value is worse than none: the observer would be told something
        specific and wrong. None leaves the template's own brightness.
        """
        from goats_tom.gpp_observation_builder import build_source_profile

        assert build_source_profile(magnitude, passband) is None


@pytest.mark.django_db()
class TestBrightnessSubstitution:
    """The trigger takes brightness from the alert, not the template."""

    def test_profile_reaches_the_clone(self, subscription, target):
        from goats_tom.models import AntaresLocus

        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id=target.name,
            ra=10.0,
            dec=20.0,
            latest_alert_id="a",
            latest_alert_magnitude=18.9,
            latest_alert_passband="g",
        )
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)

        profile = clone.call_args.kwargs["source_profile"]
        brightness = profile.point.band_normalized.brightnesses[0]
        assert brightness.value == 18.9
        assert brightness.band.value == "SLOAN_G"

    def test_magnitude_and_passband_come_from_the_same_alert(
        self, subscription, target
    ):
        """`ant_mag` wins over the locus-level magnitude.

        Pairing a magnitude from one detection with a band from another would
        misreport the brightness.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()
        alert_assignment = source.index("if alert_magnitude is not None:")
        locus_assignment = source.index(
            'newest_alert_magnitude = locus.properties.get("newest_alert_magnitude")'
        )
        assert alert_assignment > locus_assignment

    def test_missing_locus_row_passes_none(self, subscription, target):
        """No stored alert data means no brightness override."""
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["source_profile"] is None


class TestAlertBrightnessExtraction:
    """Magnitude and passband come from the newest alert's own properties."""

    def _locus(self, properties, with_alerts=True):
        from types import SimpleNamespace

        alerts = (
            [
                SimpleNamespace(
                    properties={"ant_mag": 20.0, "ant_passband": "u"}
                ),
                SimpleNamespace(properties=properties),
            ]
            if with_alerts
            else []
        )
        return SimpleNamespace(properties={}, alerts=alerts)

    def test_reads_the_newest_alert(self):
        """Not the first: both describe an individual detection."""
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        magnitude, passband = _newest_alert_brightness(
            self._locus({"ant_mag": 18.7, "ant_passband": "r"})
        )
        assert magnitude == 18.7
        assert passband == "r"

    def test_whitespace_is_stripped(self):
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        _, passband = _newest_alert_brightness(
            self._locus({"ant_mag": 18.7, "ant_passband": " g "})
        )
        assert passband == "g"

    def test_missing_properties_report_missing(self):
        """Defaulting would substitute a wrong brightness on a real target."""
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        assert _newest_alert_brightness(self._locus({})) == (None, "")
        assert _newest_alert_brightness(self._locus({}, with_alerts=False)) == (
            None,
            "",
        )

    def test_unparseable_magnitude_is_discarded(self):
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        magnitude, passband = _newest_alert_brightness(
            self._locus({"ant_mag": "not a number", "ant_passband": "g"})
        )
        assert magnitude is None
        # The passband still survives, but build_source_profile needs both, so
        # no brightness override is applied.
        assert passband == "g"

    def test_uses_antares_normalised_keys(self):
        """`ant_mag`/`ant_passband` are survey-independent.

        Survey-specific keys (ZTF's integer `fid`, say) would each need their
        own translation; these are normalised by ANTARES itself.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()
        assert 'properties.get("ant_mag")' in source
        assert 'properties.get("ant_passband")' in source


class TestPickerFieldHelp:
    """Explanations are visible, not placeholders on filled fields."""

    def _source(self):
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()

    def test_observer_notes_help_is_not_a_placeholder(self):
        """Regression test: a placeholder never shows on a pre-filled field."""
        source = self._source()
        assert "field.placeholder" not in source
        assert "#addFieldHelp" in source

    def test_brightnesses_section_is_locked(self):
        source = self._source()
        # Plural, matching the heading in fields.js -- easy to get wrong.
        assert "#section-brightnesses" in source
        # `inert`, not `disabled`: a disabled input is omitted from FormData,
        # which silently dropped these fields from the payload and made the
        # serializer reject the whole request.
        assert "section.inert = true" in source
        assert "el.disabled = true" not in source

    def test_apply_surfaces_the_server_error(self):
        """A generic failure message hid an actionable validation error."""
        source = self._source()
        assert "body?.detail" in source
        assert 'statusEl.textContent = "Could not apply these settings."' not in source

    def test_brightness_note_explains_the_substitution(self):
        assert "newest magnitude and passband" in self._source()


@pytest.mark.django_db()
class TestSaveAttributionTiming:
    """Who saved a locus must be known the moment it looks saved."""

    def test_recorded_before_light_curve_ingestion(self):
        """Otherwise the dashboard shows "Unknown" until the next poll.

        The dashboard decides "is this saved?" from the Target and "who saved
        it?" from AntaresTargetSave. Any gap between the two is a window where
        the locus appears saved by nobody -- and light curve ingestion is a
        network fetch plus several writes, so the window was wide enough to
        hit on the very first poll.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "antares_target_save.py"
        ).read_text()

        creation = source.index("target.save(extras=extras, names=aliases)")
        attribution = source.index("_record_save(locus_id, target, saved_by)", creation)
        ingestion = source.index("process_lightcurve_data", creation)
        assert attribution < ingestion, (
            "attribution must be recorded before light curve ingestion"
        )


@pytest.mark.django_db()
class TestSerializeOverridesEndpoint:
    """The template panel's save endpoint must accept what the form posts."""

    DRF = {
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework.authentication.SessionAuthentication",
            "rest_framework.authentication.TokenAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": [],
    }

    def _post(self, client, **extra):
        """Post what ObservationForm.getData() actually builds."""
        import json

        payload = {
            "gppObservationId": "o-1",
            "observerNotesTextarea": "ANTARES locus: {locus_url}",
            "hiddenObservingModeInput": "GMOS_NORTH_LONG_SLIT",
            # Multipart sends these as JSON *strings*, not objects.
            "finderCharts": json.dumps({"toAdd": [], "toDelete": []}),
            "timingWindows": json.dumps([]),
        }
        payload.update(extra)
        return client.post(
            "/api/gpp/observations/serialize-overrides/", payload
        )

    def test_json_string_payloads_are_not_a_shape_error(self, client, owner):
        """Regression test: finderCharts arrived as a string and was rejected.

        `FinderChartsSerializer` hands `data["finderCharts"]` straight to DRF,
        which needs a dict -- so a multipart JSON string produced "Expected a
        dictionary, but got str" and every save from the panel failed. The
        other two endpoints normalise it first; this one did not.
        """
        from django.test import override_settings

        client.force_login(owner)
        with override_settings(REST_FRAMEWORK=self.DRF):
            response = self._post(client)

        body = response.content.decode()
        assert "Expected a dictionary" not in body, body
        assert "finderCharts" not in body, body

    def test_endpoint_normalises_like_its_siblings(self):
        """All three callers must prepare data the same way.

        Diverging is what caused this: the preparation step is easy to omit
        and the failure appears far away, inside a nested serializer.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "api_views" / "gpp" / "observations.py"
        ).read_text()
        assert source.count("_normalize_finder_charts(normalized_data)") == 3


@pytest.mark.django_db()
class TestAutoSaveGuard:
    """Auto-save must not be permanently disabled by a stale save record."""

    def _guard(self, locus_id, owner):
        from goats_tom.tasks.ingest_antares_stream import (
            _auto_save_already_done,
        )

        return _auto_save_already_done(locus_id, owner)

    def test_skips_when_saved_and_target_exists(self, owner):
        """The normal case: repeat alerts for a saved locus are a no-op."""
        from goats_tom.models import AntaresTargetSave

        Target.objects.create(
            name="ANT1", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=owner)
        assert self._guard("ANT1", owner) is True

    def test_resaves_when_the_target_was_deleted(self, owner):
        """Regression test: this was skipped forever.

        `AntaresTargetSave` rows are never deleted -- not by clearing the
        dashboard, which removes only `AntaresLocus`, and not by deleting the
        target. Guarding on the record alone meant a locus saved once and then
        removed could never be auto-saved again, with nothing in the interface
        to explain the silence.
        """
        from goats_tom.models import AntaresTargetSave

        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=owner)
        assert self._guard("ANT1", owner) is False

    def test_saves_when_another_team_owns_the_target(self, owner):
        """A target somebody else created still needs sharing with us."""
        other = User.objects.create_user("otherteam")
        from goats_tom.models import AntaresTargetSave

        Target.objects.create(
            name="ANT1", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=other)
        assert self._guard("ANT1", owner) is False

    def test_saves_when_nothing_recorded(self, owner):
        assert self._guard("ANT-NEW", owner) is False

    def test_no_owner_means_not_done(self, db):
        assert self._guard("ANT1", None) is False


@pytest.mark.django_db()
class TestTargetDeleteClearsSaveRecords:
    """A save record must not outlive the target it describes."""

    def test_record_removed_with_the_target(self, owner):
        """Otherwise auto-save treats the locus as still saved, forever."""
        from goats_tom.models import AntaresTargetSave

        target = Target.objects.create(
            name="ANT-DEL", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-DEL", saved_by=owner)
        target.delete()
        assert not AntaresTargetSave.objects.filter(locus_id="ANT-DEL").exists()

    def test_other_records_are_untouched(self, owner):
        """Only the deleted target's records go."""
        from goats_tom.models import AntaresTargetSave

        target = Target.objects.create(
            name="ANT-A", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        Target.objects.create(
            name="ANT-B", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-A", saved_by=owner)
        AntaresTargetSave.objects.create(locus_id="ANT-B", saved_by=owner)
        target.delete()
        assert AntaresTargetSave.objects.filter(locus_id="ANT-B").exists()

    def test_auto_save_runs_again_after_deletion(self, owner):
        """The whole point: deleting a target unblocks auto-save."""
        from goats_tom.models import AntaresTargetSave
        from goats_tom.tasks.ingest_antares_stream import (
            _auto_save_already_done,
        )

        target = Target.objects.create(
            name="ANT-RE", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-RE", saved_by=owner)
        assert _auto_save_already_done("ANT-RE", owner) is True
        target.delete()
        assert _auto_save_already_done("ANT-RE", owner) is False


@pytest.mark.django_db()
class TestTriggerDecoupledFromSave:
    """Triggering must not depend on this alert having done the saving."""

    def test_triggers_for_an_already_saved_locus(self):
        """Regression test: this could never trigger.

        A locus saved earlier, by hand, or by another team skips the save --
        and triggering used to live inside the save branch, so it never ran.
        Enabling triggering on a populated dashboard did nothing for the same
        reason.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()

        save_guard = source.index("if save_all_targets and not _auto_save_already_done")
        trigger = source.index("if trigger_gemini_observations and not _already_triggered")
        between = source[save_guard:trigger]
        # The trigger must not sit in the save's else-branch any more.
        assert "else:" not in between, "triggering is still nested under the save"

    def test_trigger_has_its_own_idempotency_check(self):
        """An active locus re-alerts every few minutes."""
        from goats_tom.tasks.ingest_antares_stream import _already_triggered
        from goats_tom.models import (
            AntaresStreamSubscription,
            GeminiTriggerRecord,
        )

        sub = AntaresStreamSubscription.objects.create(topics=["t"])
        assert _already_triggered(sub.pk, "ANT1") is False
        GeminiTriggerRecord.objects.create(subscription=sub, locus_id="ANT1")
        assert _already_triggered(sub.pk, "ANT1") is True

    def test_idempotency_is_per_subscription(self):
        """Another team's trigger must not block ours."""
        from goats_tom.tasks.ingest_antares_stream import _already_triggered
        from goats_tom.models import (
            AntaresStreamSubscription,
            GeminiTriggerRecord,
        )

        mine = AntaresStreamSubscription.objects.create(topics=["a"])
        theirs = AntaresStreamSubscription.objects.create(topics=["b"])
        GeminiTriggerRecord.objects.create(subscription=theirs, locus_id="ANT1")
        assert _already_triggered(mine.pk, "ANT1") is False


@pytest.mark.django_db()
class TestTriggerVisibility:
    """Trigger outcomes must be visible somewhere.

    Regression test: the model, the guards and the whole pipeline existed but
    nothing was ever surfaced, so a trigger that succeeded, was skipped, or
    failed all looked identical from the interface -- namely, like nothing had
    happened at all.
    """

    @pytest.fixture()
    def dashboard(self, owner):
        from goats_tom.models import AntaresLocus, AntaresStreamSubscription

        subscription = AntaresStreamSubscription.objects.create(
            owner=owner,
            topics=["t"],
            trigger_gemini_observations=True,
            gpp_program_id="p-1",
            gpp_observation_id="o-1",
            max_triggers=10,
        )
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT-VIS",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a",
        )
        return subscription

    def test_success_is_shown(self, client, owner, dashboard):
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_SUCCESS,
            gpp_observation_id="o-new",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Triggered" in content
        assert b"o-new" in content

    def test_skip_reason_is_shown(self, client, owner, dashboard):
        """A skip without its reason is as opaque as no message at all."""
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_SKIPPED,
            detail="Trigger limit reached.",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Skipped" in content
        assert b"Trigger limit reached." in content

    def test_failure_is_shown(self, client, owner, dashboard):
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="GPP unreachable.",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Failed" in content

    def test_untriggered_locus_shows_a_placeholder(
        self, client, owner, dashboard
    ):
        """A locus with no attempt reads as such, not as blank.

        The per-locus column is the only report now: a summary line in the
        polled status banner accumulated a copy on every poll, because
        `hx-swap="outerHTML"` replaces only the element it is declared on.
        """
        from django.urls import reverse

        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Gemini Trigger" in content
        assert b"No Gemini trigger has been attempted" in content


class TestPassbandMapping:
    """ANTARES letters map to GPP's Sloan band names."""

    @pytest.mark.parametrize(
        ("antares", "expected"),
        [
            ("u", "SLOAN_U"),
            ("g", "SLOAN_G"),
            ("r", "SLOAN_R"),
            ("i", "SLOAN_I"),
            ("z", "SLOAN_Z"),
            ("G", "SLOAN_G"),
            ("R", "SLOAN_R"),
            (" g ", "SLOAN_G"),
        ],
    )
    def test_case_insensitive_mapping(self, antares, expected):
        """Surveys are inconsistent about case, so both must work."""
        from goats_tom.gpp_observation_builder import build_source_profile

        profile = build_source_profile(18.4, antares)
        assert profile.point.band_normalized.brightnesses[0].band.value == expected

    def test_magnitude_and_units(self):
        from goats_tom.gpp_observation_builder import build_source_profile

        brightness = build_source_profile(
            19.25, "r"
        ).point.band_normalized.brightnesses[0]
        assert brightness.value == 19.25
        # ANTARES reports AB magnitudes.
        assert brightness.units.value == "AB_MAGNITUDE"

    @pytest.mark.parametrize(
        ("magnitude", "passband"),
        [(None, "g"), (18.4, ""), (18.4, None), (18.4, "w"), (None, None)],
    )
    def test_incomplete_input_yields_no_override(self, magnitude, passband):
        """A partial or unmappable brightness must not be substituted.

        Brightness describes a real object on a real observation, so a guessed
        value is worse than none: the observer would be told something
        specific and wrong. None leaves the template's own brightness.
        """
        from goats_tom.gpp_observation_builder import build_source_profile

        assert build_source_profile(magnitude, passband) is None


@pytest.mark.django_db()
class TestBrightnessSubstitution:
    """The trigger takes brightness from the alert, not the template."""

    def test_profile_reaches_the_clone(self, subscription, target):
        from goats_tom.models import AntaresLocus

        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id=target.name,
            ra=10.0,
            dec=20.0,
            latest_alert_id="a",
            latest_alert_magnitude=18.9,
            latest_alert_passband="g",
        )
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)

        profile = clone.call_args.kwargs["source_profile"]
        brightness = profile.point.band_normalized.brightnesses[0]
        assert brightness.value == 18.9
        assert brightness.band.value == "SLOAN_G"

    def test_magnitude_and_passband_come_from_the_same_alert(
        self, subscription, target
    ):
        """`ant_mag` wins over the locus-level magnitude.

        Pairing a magnitude from one detection with a band from another would
        misreport the brightness.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()
        alert_assignment = source.index("if alert_magnitude is not None:")
        locus_assignment = source.index(
            'newest_alert_magnitude = locus.properties.get("newest_alert_magnitude")'
        )
        assert alert_assignment > locus_assignment

    def test_missing_locus_row_passes_none(self, subscription, target):
        """No stored alert data means no brightness override."""
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["source_profile"] is None


class TestAlertBrightnessExtraction:
    """Magnitude and passband come from the newest alert's own properties."""

    def _locus(self, properties, with_alerts=True):
        from types import SimpleNamespace

        alerts = (
            [
                SimpleNamespace(
                    properties={"ant_mag": 20.0, "ant_passband": "u"}
                ),
                SimpleNamespace(properties=properties),
            ]
            if with_alerts
            else []
        )
        return SimpleNamespace(properties={}, alerts=alerts)

    def test_reads_the_newest_alert(self):
        """Not the first: both describe an individual detection."""
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        magnitude, passband = _newest_alert_brightness(
            self._locus({"ant_mag": 18.7, "ant_passband": "r"})
        )
        assert magnitude == 18.7
        assert passband == "r"

    def test_whitespace_is_stripped(self):
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        _, passband = _newest_alert_brightness(
            self._locus({"ant_mag": 18.7, "ant_passband": " g "})
        )
        assert passband == "g"

    def test_missing_properties_report_missing(self):
        """Defaulting would substitute a wrong brightness on a real target."""
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        assert _newest_alert_brightness(self._locus({})) == (None, "")
        assert _newest_alert_brightness(self._locus({}, with_alerts=False)) == (
            None,
            "",
        )

    def test_unparseable_magnitude_is_discarded(self):
        from goats_tom.tasks.ingest_antares_stream import (
            _newest_alert_brightness,
        )

        magnitude, passband = _newest_alert_brightness(
            self._locus({"ant_mag": "not a number", "ant_passband": "g"})
        )
        assert magnitude is None
        # The passband still survives, but build_source_profile needs both, so
        # no brightness override is applied.
        assert passband == "g"

    def test_uses_antares_normalised_keys(self):
        """`ant_mag`/`ant_passband` are survey-independent.

        Survey-specific keys (ZTF's integer `fid`, say) would each need their
        own translation; these are normalised by ANTARES itself.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()
        assert 'properties.get("ant_mag")' in source
        assert 'properties.get("ant_passband")' in source


class TestPickerFieldHelp:
    """Explanations are visible, not placeholders on filled fields."""

    def _source(self):
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "static" / "js" / "gpp"
            / "template_picker.js"
        ).read_text()

    def test_observer_notes_help_is_not_a_placeholder(self):
        """Regression test: a placeholder never shows on a pre-filled field."""
        source = self._source()
        assert "field.placeholder" not in source
        assert "#addFieldHelp" in source

    def test_brightnesses_section_is_locked(self):
        source = self._source()
        # Plural, matching the heading in fields.js -- easy to get wrong.
        assert "#section-brightnesses" in source
        # `inert`, not `disabled`: a disabled input is omitted from FormData,
        # which silently dropped these fields from the payload and made the
        # serializer reject the whole request.
        assert "section.inert = true" in source
        assert "el.disabled = true" not in source

    def test_apply_surfaces_the_server_error(self):
        """A generic failure message hid an actionable validation error."""
        source = self._source()
        assert "body?.detail" in source
        assert 'statusEl.textContent = "Could not apply these settings."' not in source

    def test_brightness_note_explains_the_substitution(self):
        assert "newest magnitude and passband" in self._source()


@pytest.mark.django_db()
class TestSaveAttributionTiming:
    """Who saved a locus must be known the moment it looks saved."""

    def test_recorded_before_light_curve_ingestion(self):
        """Otherwise the dashboard shows "Unknown" until the next poll.

        The dashboard decides "is this saved?" from the Target and "who saved
        it?" from AntaresTargetSave. Any gap between the two is a window where
        the locus appears saved by nobody -- and light curve ingestion is a
        network fetch plus several writes, so the window was wide enough to
        hit on the very first poll.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "antares_target_save.py"
        ).read_text()

        creation = source.index("target.save(extras=extras, names=aliases)")
        attribution = source.index("_record_save(locus_id, target, saved_by)", creation)
        ingestion = source.index("process_lightcurve_data", creation)
        assert attribution < ingestion, (
            "attribution must be recorded before light curve ingestion"
        )


@pytest.mark.django_db()
class TestSerializeOverridesEndpoint:
    """The template panel's save endpoint must accept what the form posts."""

    DRF = {
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework.authentication.SessionAuthentication",
            "rest_framework.authentication.TokenAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": [],
    }

    def _post(self, client, **extra):
        """Post what ObservationForm.getData() actually builds."""
        import json

        payload = {
            "gppObservationId": "o-1",
            "observerNotesTextarea": "ANTARES locus: {locus_url}",
            "hiddenObservingModeInput": "GMOS_NORTH_LONG_SLIT",
            # Multipart sends these as JSON *strings*, not objects.
            "finderCharts": json.dumps({"toAdd": [], "toDelete": []}),
            "timingWindows": json.dumps([]),
        }
        payload.update(extra)
        return client.post(
            "/api/gpp/observations/serialize-overrides/", payload
        )

    def test_json_string_payloads_are_not_a_shape_error(self, client, owner):
        """Regression test: finderCharts arrived as a string and was rejected.

        `FinderChartsSerializer` hands `data["finderCharts"]` straight to DRF,
        which needs a dict -- so a multipart JSON string produced "Expected a
        dictionary, but got str" and every save from the panel failed. The
        other two endpoints normalise it first; this one did not.
        """
        from django.test import override_settings

        client.force_login(owner)
        with override_settings(REST_FRAMEWORK=self.DRF):
            response = self._post(client)

        body = response.content.decode()
        assert "Expected a dictionary" not in body, body
        assert "finderCharts" not in body, body

    def test_endpoint_normalises_like_its_siblings(self):
        """All three callers must prepare data the same way.

        Diverging is what caused this: the preparation step is easy to omit
        and the failure appears far away, inside a nested serializer.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "api_views" / "gpp" / "observations.py"
        ).read_text()
        assert source.count("_normalize_finder_charts(normalized_data)") == 3


@pytest.mark.django_db()
class TestAutoSaveGuard:
    """Auto-save must not be permanently disabled by a stale save record."""

    def _guard(self, locus_id, owner):
        from goats_tom.tasks.ingest_antares_stream import (
            _auto_save_already_done,
        )

        return _auto_save_already_done(locus_id, owner)

    def test_skips_when_saved_and_target_exists(self, owner):
        """The normal case: repeat alerts for a saved locus are a no-op."""
        from goats_tom.models import AntaresTargetSave

        Target.objects.create(
            name="ANT1", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=owner)
        assert self._guard("ANT1", owner) is True

    def test_resaves_when_the_target_was_deleted(self, owner):
        """Regression test: this was skipped forever.

        `AntaresTargetSave` rows are never deleted -- not by clearing the
        dashboard, which removes only `AntaresLocus`, and not by deleting the
        target. Guarding on the record alone meant a locus saved once and then
        removed could never be auto-saved again, with nothing in the interface
        to explain the silence.
        """
        from goats_tom.models import AntaresTargetSave

        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=owner)
        assert self._guard("ANT1", owner) is False

    def test_saves_when_another_team_owns_the_target(self, owner):
        """A target somebody else created still needs sharing with us."""
        other = User.objects.create_user("otherteam")
        from goats_tom.models import AntaresTargetSave

        Target.objects.create(
            name="ANT1", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT1", saved_by=other)
        assert self._guard("ANT1", owner) is False

    def test_saves_when_nothing_recorded(self, owner):
        assert self._guard("ANT-NEW", owner) is False

    def test_no_owner_means_not_done(self, db):
        assert self._guard("ANT1", None) is False


@pytest.mark.django_db()
class TestTargetDeleteClearsSaveRecords:
    """A save record must not outlive the target it describes."""

    def test_record_removed_with_the_target(self, owner):
        """Otherwise auto-save treats the locus as still saved, forever."""
        from goats_tom.models import AntaresTargetSave

        target = Target.objects.create(
            name="ANT-DEL", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-DEL", saved_by=owner)
        target.delete()
        assert not AntaresTargetSave.objects.filter(locus_id="ANT-DEL").exists()

    def test_other_records_are_untouched(self, owner):
        """Only the deleted target's records go."""
        from goats_tom.models import AntaresTargetSave

        target = Target.objects.create(
            name="ANT-A", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        Target.objects.create(
            name="ANT-B", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-A", saved_by=owner)
        AntaresTargetSave.objects.create(locus_id="ANT-B", saved_by=owner)
        target.delete()
        assert AntaresTargetSave.objects.filter(locus_id="ANT-B").exists()

    def test_auto_save_runs_again_after_deletion(self, owner):
        """The whole point: deleting a target unblocks auto-save."""
        from goats_tom.models import AntaresTargetSave
        from goats_tom.tasks.ingest_antares_stream import (
            _auto_save_already_done,
        )

        target = Target.objects.create(
            name="ANT-RE", type=Target.SIDEREAL, ra=1.0, dec=2.0
        )
        AntaresTargetSave.objects.create(locus_id="ANT-RE", saved_by=owner)
        assert _auto_save_already_done("ANT-RE", owner) is True
        target.delete()
        assert _auto_save_already_done("ANT-RE", owner) is False


@pytest.mark.django_db()
class TestTriggerDecoupledFromSave:
    """Triggering must not depend on this alert having done the saving."""

    def test_triggers_for_an_already_saved_locus(self):
        """Regression test: this could never trigger.

        A locus saved earlier, by hand, or by another team skips the save --
        and triggering used to live inside the save branch, so it never ran.
        Enabling triggering on a populated dashboard did nothing for the same
        reason.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "tasks" / "ingest_antares_stream.py"
        ).read_text()

        save_guard = source.index("if save_all_targets and not _auto_save_already_done")
        trigger = source.index("if trigger_gemini_observations and not _already_triggered")
        between = source[save_guard:trigger]
        # The trigger must not sit in the save's else-branch any more.
        assert "else:" not in between, "triggering is still nested under the save"

    def test_trigger_has_its_own_idempotency_check(self):
        """An active locus re-alerts every few minutes."""
        from goats_tom.tasks.ingest_antares_stream import _already_triggered
        from goats_tom.models import (
            AntaresStreamSubscription,
            GeminiTriggerRecord,
        )

        sub = AntaresStreamSubscription.objects.create(topics=["t"])
        assert _already_triggered(sub.pk, "ANT1") is False
        GeminiTriggerRecord.objects.create(subscription=sub, locus_id="ANT1")
        assert _already_triggered(sub.pk, "ANT1") is True

    def test_idempotency_is_per_subscription(self):
        """Another team's trigger must not block ours."""
        from goats_tom.tasks.ingest_antares_stream import _already_triggered
        from goats_tom.models import (
            AntaresStreamSubscription,
            GeminiTriggerRecord,
        )

        mine = AntaresStreamSubscription.objects.create(topics=["a"])
        theirs = AntaresStreamSubscription.objects.create(topics=["b"])
        GeminiTriggerRecord.objects.create(subscription=theirs, locus_id="ANT1")
        assert _already_triggered(mine.pk, "ANT1") is False


@pytest.mark.django_db()
class TestTriggerVisibility:
    """Trigger outcomes must be visible somewhere.

    Regression test: the model, the guards and the whole pipeline existed but
    nothing was ever surfaced, so a trigger that succeeded, was skipped, or
    failed all looked identical from the interface -- namely, like nothing had
    happened at all.
    """

    @pytest.fixture()
    def dashboard(self, owner):
        from goats_tom.models import AntaresLocus, AntaresStreamSubscription

        subscription = AntaresStreamSubscription.objects.create(
            owner=owner,
            topics=["t"],
            trigger_gemini_observations=True,
            gpp_program_id="p-1",
            gpp_observation_id="o-1",
            max_triggers=10,
        )
        AntaresLocus.objects.create(
            subscription=subscription,
            locus_id="ANT-VIS",
            ra=1.0,
            dec=2.0,
            latest_alert_id="a",
        )
        return subscription

    def test_success_is_shown(self, client, owner, dashboard):
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_SUCCESS,
            gpp_observation_id="o-new",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Triggered" in content
        assert b"o-new" in content

    def test_skip_reason_is_shown(self, client, owner, dashboard):
        """A skip without its reason is as opaque as no message at all."""
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_SKIPPED,
            detail="Trigger limit reached.",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Skipped" in content
        assert b"Trigger limit reached." in content

    def test_failure_is_shown(self, client, owner, dashboard):
        from django.urls import reverse

        from goats_tom.models import GeminiTriggerRecord

        GeminiTriggerRecord.objects.create(
            subscription=dashboard,
            locus_id="ANT-VIS",
            status=GeminiTriggerRecord.STATUS_FAILED,
            detail="GPP unreachable.",
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Failed" in content

    def test_untriggered_locus_shows_a_placeholder(
        self, client, owner, dashboard
    ):
        """A locus with no attempt reads as such, not as blank.

        The per-locus column is the only report now: a summary line in the
        polled status banner accumulated a copy on every poll, because
        `hx-swap="outerHTML"` replaces only the element it is declared on.
        """
        from django.urls import reverse

        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Gemini Trigger" in content
        assert b"No Gemini trigger has been attempted" in content

    def test_summary_hidden_when_triggering_is_off(self, client, owner):
        from django.urls import reverse

        from goats_tom.models import AntaresStreamSubscription

        AntaresStreamSubscription.objects.create(
            owner=owner, topics=["t"], trigger_gemini_observations=False
        )
        client.force_login(owner)
        content = client.get(reverse("antares-locus-dashboard")).content
        assert b"Gemini triggering" not in content


class TestCloneCalculationRecovery:
    """A clone whose reply fails must not orphan the observation it created.

    GPP computes an observation's workflow state in the background, and the
    clone mutation selects that field. Asked too soon it errors -- but the
    observation exists, leaving it visible in Explore with no record in GOATS.
    """

    def _recover(self, message):
        from goats_tom.api_views.gpp.observations import GPPObservationViewSet

        return GPPObservationViewSet._observation_id_from_clone_error(
            RuntimeError(message)
        )

    def test_recovers_the_id_from_the_message(self):
        assert (
            self._recover(
                "The background calculation has not (yet) produced a value "
                "for observation o-1a2b"
            )
            == "o-1a2b"
        )

    def test_ignores_unrelated_errors(self):
        """Only this specific, known-safe case is recovered from.

        Any other failure may mean nothing was created, and inventing an id
        would be far worse than reporting the error.
        """
        assert self._recover("Permission denied") is None
        assert self._recover("Connection reset by peer") is None

    def test_returns_none_when_no_id_is_present(self):
        """Parsing an error string is brittle; a miss must degrade safely."""
        assert (
            self._recover("The background calculation has not produced a value")
            is None
        )

    def test_clone_failure_is_tolerated_not_swallowed(self):
        """The recovery path must re-raise anything it cannot identify."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "api_views" / "gpp" / "observations.py"
        ).read_text()
        block = source[source.index("except Exception as clone_error:") :][:600]
        assert "raise" in block, "an unrecognised clone failure must propagate"


class TestCloneRecoveryCompletesTheSave:
    """Recovering from a failed clone reply must not break the save step.

    Regression test: the recovery set the observation *id* but left the
    observation details unbound, so the save stage failed with "cannot access
    local variable 'new_observation'" -- turning a recoverable situation into
    a different failure, with the observation still orphaned in GPP.
    """

    def _source(self):
        from pathlib import Path

        return (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "api_views" / "gpp" / "observations.py"
        ).read_text()

    def test_recovery_binds_the_observation_variable(self):
        """Every path out of the clone must define it."""
        source = self._source()
        # Bounded by the next statement rather than a character count, so
        # the assertion cannot silently drift out of range as comments grow.
        start = source.index("except Exception as clone_error:")
        end = source.index("if clone_observation_result is not None:", start)
        assert "new_observation = None" in source[start:end]

    def test_details_are_fetched_before_saving(self):
        """A stub id is not enough: the record needs the reference label."""
        source = self._source()
        save_block = source[source.index("Save the created observation to GOATS") :][:1400]
        assert "client.observation.get_by_id" in save_block

    def test_fetch_happens_after_the_workflow_step(self):
        """That step already waits for the calculation that caused this.

        Fetching earlier would hit the same pending calculation and fail
        again.
        """
        source = self._source()
        workflow = source.index("update_by_id_with_retry")
        fetch = source.index(
            "Save the created observation to GOATS"
        )
        assert workflow < fetch

    def test_failed_refetch_does_not_crash(self):
        """A re-fetch failure must be reported, not raised.

        The observation exists either way; losing the GOATS record is bad but
        an unhandled exception mid-flow is worse.
        """
        source = self._source()
        block = source[source.index("Could not re-fetch observation") - 400 :][:800]
        assert "except Exception:" in block
        assert "logger.exception" in block


@pytest.mark.django_db()
class TestWorkflowStateFromTemplate:
    """The State chosen in the template editor must be honoured."""

    def test_stored_state_is_used(self, subscription, target):
        """Regression test: READY was forced, discarding the user's choice.

        The editor presents State as editable, so overriding it silently was
        worse than not offering it.
        """
        subscription.gpp_workflow_state = "DEFINED"
        subscription.save()
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["workflow_state"] == "DEFINED"

    def test_blank_means_ready(self, subscription, target):
        """READY stays the default for automatic triggering."""
        with _snapshot(), patch("gpp_client.GPPClient"):
            with patch(
                "goats_tom.gpp_observation_builder.clone_observation_for_target",
                return_value={"target_id": "t", "observation_id": "o"},
            ) as clone:
                trigger_gemini_observation(subscription, target.name, target)
        assert clone.call_args.kwargs["workflow_state"] is None

    def test_builder_accepts_a_string(self):
        """Stored values are strings, not enum members."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "gpp_observation_builder.py"
        ).read_text()
        assert "isinstance(workflow_state, str)" in source

    def test_unknown_state_falls_back_rather_than_raising(self):
        """The observation already exists by then; leaving it stateless is
        worse than using the default."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "gpp_observation_builder.py"
        ).read_text()
        block = source[source.index("isinstance(workflow_state, str)") :][:600]
        assert "except ValueError" in block
        assert "READY" in block


class TestDashboardStatusPartial:
    """The polled banner must not accumulate content."""

    def test_no_content_outside_the_swapped_element(self):
        """Regression test: a summary line repeated on every poll.

        `hx-swap="outerHTML"` replaces only the element it is declared on, so
        anything rendered after that element's closing tag is appended afresh
        each time.
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "src" / "goats_tom" / "templates" / "partials"
            / "antares_dashboard_status.html"
        ).read_text()
        # Everything after the last </div> should be whitespace only.
        tail = source[source.rindex("</div>") + len("</div>") :]
        assert not tail.strip(), f"content outside the swapped element: {tail!r}"
