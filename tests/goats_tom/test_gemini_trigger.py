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


def _snapshot(allocated=10.0, charged=0.0, execution=1.0):
    """Patch the programme snapshot with given hours."""
    return patch(
        "goats_tom.gemini_trigger._fetch_program_snapshot",
        return_value=(allocated, charged, execution),
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

    def test_execution_time_is_stored(self, subscription, target):
        """Kept so the running total survives the observation being deleted."""
        with _snapshot(execution=2.5), _clone_ok(), patch("gpp_client.GPPClient"):
            record = trigger_gemini_observation(
                subscription, target.name, target
            )
        assert record.execution_time_hours == 2.5


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
class TestAllocationGuard:
    """No partial overrun of the programme's grant."""

    def test_refuses_when_it_would_not_fit(self, subscription, target):
        """0.5 h left, 0.7 h needed -- refused, not submitted hopefully.

        A submission GPP rejected would still leave a cloned target and
        observation behind for somebody to find and delete.
        """
        with _snapshot(allocated=10.0, charged=9.5, execution=0.7):
            with patch("gpp_client.GPPClient"), _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SKIPPED
        assert "not enough time" in record.detail.lower()
        clone.assert_not_called()

    def test_allows_an_exact_fit(self, subscription, target):
        """Equal is within the allocation, not over it."""
        with _snapshot(allocated=10.0, charged=9.0, execution=1.0):
            with patch("gpp_client.GPPClient"), _clone_ok():
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS

    def test_unreachable_gpp_refuses_rather_than_guesses(
        self, subscription, target
    ):
        """Triggering blind would defeat the guard entirely."""
        from goats_tom.gemini_trigger import TriggerFailed

        with patch(
            "goats_tom.gemini_trigger._fetch_program_snapshot",
            side_effect=TriggerFailed("GPP unreachable"),
        ):
            with patch("gpp_client.GPPClient"), _clone_ok() as clone:
                record = trigger_gemini_observation(
                    subscription, target.name, target
                )
        assert record.status == GeminiTriggerRecord.STATUS_FAILED
        clone.assert_not_called()


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

    def test_rejected_without_auto_save(self):
        """Triggering needs a saved target to point the observation at.

        The consumer only reaches the trigger inside its auto-save branch, so
        without auto-save the checkbox would appear on and do nothing -- with
        no error and not even a skipped trigger record to explain it.
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
        assert not form.is_valid()
        assert "trigger_gemini_observations" in form.errors
        assert "save" in str(form.errors["trigger_gemini_observations"]).lower()

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
        assert "el.disabled = true" in source

    def test_brightness_note_explains_the_substitution(self):
        assert "newest magnitude and passband" in self._source()
