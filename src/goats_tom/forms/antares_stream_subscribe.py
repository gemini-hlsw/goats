"""Form for subscribing to ANTARES Kafka stream topics."""

__all__ = ["AntaresStreamSubscribeForm"]

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.urls import reverse
from django.utils.safestring import mark_safe

from goats_tom.antares_locus_handler import (
    LocusHandlerError,
    is_effectively_blank,
    validate_handler_code,
)
from goats_tom.models.antares_stream_subscription import (
    DEFAULT_MAX_LOCI,
    DEFAULT_MAX_TRIGGERS,
)


class AntaresStreamSubscribeForm(forms.Form):
    """Collects a comma-separated topic list, two toggleable checkbox
    options (one now operational, one still a no-op), and optional custom
    locus-handler code for the ANTARES Kafka stream consumer.

    Attributes
    ----------
    topics : `forms.CharField`
        Comma-separated Kafka topic names, e.g.
        ``"extragalactic_staging, nuclear_transient_staging"``.
    consumer_group : `forms.CharField`
        Optional *suffix* for this subscription's Kafka consumer group
        name. Set here (not in the Credential Manager) since it changes
        far more often than the API credentials -- e.g. to force a full
        replay via a brand-new group. Only ever a suffix: the effective
        name is generated per-subscription, so two users cannot end up
        sharing a consumer group. See
        `goats_tom.models.AntaresStreamSubscription.resolved_consumer_group`.
    save_all_targets : `forms.BooleanField`
        Checkbox, unchecked by default. When checked, every newly-ingested
        locus (not already saved) is saved as a GOATS `Target`, including
        its light curve -- see
        `goats_tom.antares_target_save.save_locus_as_target`. Uses a
        checkbox rather than a radio button so it can actually be turned
        back off after being turned on -- a single-option radio group has
        no way to deselect itself once clicked, which is a general HTML
        limitation, not specific to this form.
    trigger_gemini_observations : `forms.BooleanField`
        Checkbox, unchecked by default. Not yet wired to any behavior --
        checking it currently does nothing.
    handler_code : `forms.CharField`
        Optional Python function, ``def myfilter(locus): ...``, run
        against each locus as an additional filter beyond the topic
        subscription. See `goats_tom.antares_locus_handler` for the
        execution model, pre-bound libraries, and restrictions. Left
        blank, every locus on the subscribed topics is kept.

    """

    topics = forms.CharField(
        label="Kafka topics (comma separated)",
        widget=forms.TextInput(
            attrs={
                "id": "id_topics",
                "placeholder": "extragalactic_staging, nuclear_transient_staging",
            }
        ),
        help_text=mark_safe(
            "One or more ANTARES Kafka topic names, separated by commas. "
            "If a topic-selection list is available, use it, or type/paste "
            "names directly. Refer <a href=\"https://nsf-noirlab.gitlab.io/"
            'csdc/antares/devkit/reference/filters/" target="_blank" '
            'rel="noopener noreferrer">here</a> for the filters running '
            "on ANTARES."
        ),
    )
    consumer_group = forms.CharField(
        label="Kafka group suffix (optional)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. replay-2"}),
        help_text=(
            "Optional. Appended to a group name unique to your subscription. "
            "Enter a new value to replay from the earliest available message."
        ),
    )
    save_all_targets = forms.BooleanField(
        label="Automatically save all ingested loci as targets",
        required=False,
        help_text=(
            "Only applies to loci ingested after this is enabled."
        ),
    )
    trigger_gemini_observations = forms.BooleanField(
        label="Automatically trigger Gemini observations",
        required=False,
        help_text=mark_safe(
            "Requires stored {gpp_credentials_link} and auto-saving targets above."
        ),
    )
    # Real starting content for an empty editor, not a visual placeholder.
    # Previously the example was a CSS overlay drawn over Ace, which looked
    # like text but could not be edited, selected or copied -- a user wanting
    # to start from it had to retype it. As actual content it is immediately
    # editable.
    #
    # Deliberately a skeleton that keeps everything (`return True`) rather
    # than the full worked example: this text is submitted like any other
    # field value, so a user who ignores it saves it as their handler. A
    # skeleton that keeps every locus is a harmless no-op if left alone,
    # whereas the worked example would silently filter their stream on
    # magnitude without them having asked for it. The full example lives in
    # the help text instead.
    gpp_program_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_program_id"}),
    )
    gpp_observation_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_observation_id"}),
    )
    gpp_observation_overrides = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_observation_overrides"}),
    )
    gpp_workflow_state = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_workflow_state"}),
    )
    # The target half of the template panel's configuration. Collected by the
    # same picker as the observation overrides but previously discarded, which
    # left automatic triggering unable to reproduce what the picker showed.
    gpp_target_overrides = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_target_overrides"}),
    )
    gpp_target_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_target_id"}),
    )
    gpp_instrument = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_gpp_instrument"}),
    )
    max_triggers = forms.IntegerField(
        label="Maximum Gemini observations to create",
        required=False,
        min_value=0,
        # Pre-filled, because blank means *no limit* and an empty box on a
        # fresh page therefore handed out an unlimited allowance to anyone who
        # never noticed the field. A PI who genuinely wants no cap has to clear
        # it deliberately.
        initial=DEFAULT_MAX_TRIGGERS,
        # A small number needs a small box. Full-width looked like a mistake
        # next to the checkboxes, and implied a longer value was expected.
        widget=forms.NumberInput(attrs={"style": "max-width: 10rem;"}),
        help_text=(
            "Total for this ingestion run. Resets when you restart ingestion. "
            "Leave blank for no limit. Triggering stops when the limit is "
            "reached; ingestion continues."
        ),
    )

    max_loci = forms.IntegerField(
        # "blank for no limit" lives in the label rather than a `help_text`
        # line of its own: it is a property of the field, not advice about
        # it, and a whole rendered line for four words is not worth it.
        label="Maximum loci to keep on the dashboard (leave blank for no limit)",
        required=False,
        min_value=1,
        # Pre-filled for the same reason as `max_triggers`: blank means *no
        # limit*, so an empty box on a fresh page quietly grants an unbounded
        # dashboard to anyone who never noticed the field.
        initial=DEFAULT_MAX_LOCI,
        widget=forms.NumberInput(attrs={"style": "max-width: 10rem;"}),
    )

    use_handler_code = forms.BooleanField(
        # This checkbox is the editor's header: the separate "Custom locus
        # handler (optional)" label below it said the same thing again, and
        # the two stacked with a gap between them. `handler_code` therefore
        # renders with no label of its own -- see below.
        label="Use a custom locus handler",
        required=False,
    )

    HANDLER_CODE_SKELETON = (
        "def myfilter(locus):\n"
        "    #\n"
        "    # Example -- keep only alerts brighter than magnitude 19:\n"
        "    #     mag = locus.properties.get(\"newest_alert_magnitude\") or 99\n"
        "    #     if mag > 19:\n"
        "    #         return False\n"
        "    #\n"
        "    # Query Rubin catalogs (needs a stored RSP access token):\n"
        "    #     query = (\n"
        "    #         \"SELECT objectId FROM dp1.Object WHERE CONTAINS(\"\n"
        "    #         \"POINT('ICRS', coord_ra, coord_dec), \"\n"
        "    #         f\"CIRCLE('ICRS', {locus.ra}, {locus.dec}, 0.002)) = 1\"\n"
        "    #     )\n"
        "    #     if len(RSP_tap_service.run_async(query).to_table()) > 0:\n"
        "    #         return False\n"
        "\n"
        "    return True"
    )

    handler_code = forms.CharField(
        # Deliberately unlabelled: the checkbox immediately above names this
        # field, and repeating it cost two lines and a gap for no meaning.
        label="",
        required=False,
        widget=forms.Textarea(
            attrs={
                "id": "id_handler_code",
                "rows": 14,
                "class": "font-monospace antares-handler-code-raw",
                "spellcheck": "false",
            }
        ),
        help_text=mark_safe(
            "Optional. Define <code>myfilter(locus)</code> returning "
            "True (keep) or False (skip). See "
            '<a href="https://nsf-noirlab.gitlab.io/csdc/antares/client/'
            'api.html#antares_client.models.Locus" target="_blank" '
            'rel="noopener noreferrer">the Locus API</a> for available '
            "attributes. If running locally, 'import' is blocked, along "
            "with file access, eval/exec, but numpy, pandas, astropy, and "
            "astroquery are available by name. <code>RSP_tap_service</code> "
            "(if you've stored an {rsp_token_link}) queries Rubin catalog "
            'data. See <a href="https://sdm-schemas.lsst.io/" '
            'target="_blank" rel="noopener noreferrer">here</a> for tables '
            "and schemas for Rubin data products."
        ),
    )

    def __init__(
        self,
        *args,
        available_topics: list[str] | None = None,
        user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.available_topics = available_topics or []
        self.user = user
        self.helper = FormHelper()
        submit = Submit("submit", "Start ingesting")
        # Identified so the page can disable it while the configuration is
        # incomplete; see antares_stream_subscribe.html.
        submit.field_classes += " antares-submit"
        self.helper.add_input(submit)
        # Errors are shown via a unified banner in the template (the same
        # one used for runtime handler failures), not crispy's default
        # inline per-field rendering -- avoids showing the same error
        # twice in two different visual styles.
        self.helper.form_show_errors = False

        # help_text is defined once, at class-body level, with no access
        # to a specific request/user -- but the RSP token storage link
        # needs a specific user's pk (`user-rsp-tap-login` takes one),
        # which we only have per-instance, from `user`
        # (== request.user, passed in by the view). Filled in here,
        # rather than in the static help_text string above, for that
        # reason.
        if self.user is not None and self.user.pk:
            rsp_token_link = mark_safe(
                '<a href="{}" target="_blank" '
                'rel="noopener noreferrer">RSP access token</a>'.format(
                    reverse(
                        "user-rsp-tap-login", args=[self.user.pk]
                    )
                )
            )
        else:
            rsp_token_link = "RSP access token"
        if self.user is not None and self.user.pk:
            gpp_credentials_link = (
                '<a href="{}">GPP credentials</a>'.format(
                    reverse("user-gpp-login", args=[self.user.pk])
                )
            )
        else:
            gpp_credentials_link = "GPP credentials"
        self.fields["trigger_gemini_observations"].help_text = mark_safe(
            self.fields["trigger_gemini_observations"].help_text.format(
                gpp_credentials_link=gpp_credentials_link
            )
        )

        self.fields["handler_code"].help_text = mark_safe(
            self.fields["handler_code"].help_text.format(
                rsp_token_link=rsp_token_link
            )
        )

        # Seed an empty editor with the skeleton, so it arrives as real,
        # editable text rather than a CSS overlay that only looked like text.
        # Only when nothing else supplies a value: an existing subscription's
        # handler, or a draft being recovered after a failed submission, must
        # never be overwritten with boilerplate. Skipped for a bound form,
        # where the value comes from the submission itself.
        if not self.is_bound:
            existing = self.initial.get("handler_code")
            if not existing:
                self.initial["handler_code"] = self.HANDLER_CODE_SKELETON
            # Ticked only when there is a real handler to run. Derived from
            # the code rather than stored separately, so the checkbox cannot
            # disagree with what the consumer will actually do.
            self.initial["use_handler_code"] = bool(
                existing and not is_effectively_blank(existing)
            )

    def clean_topics(self) -> list[str]:
        """Split and clean the comma-separated topics field.

        Returns
        -------
        list of str
            Non-empty, whitespace-trimmed topic names.

        Raises
        ------
        forms.ValidationError
            If no valid topic names remain after cleaning.
        """
        raw = self.cleaned_data["topics"]
        topics = [t.strip() for t in raw.split(",") if t.strip()]
        if not topics:
            raise forms.ValidationError("Enter at least one topic name.")
        return topics

    def clean_gpp_target_overrides(self):
        """Parse the target overrides posted by the template panel.

        Returns
        -------
        dict
            The target properties, or ``{}`` if none were set.

        Raises
        ------
        `forms.ValidationError`
            If the value is not a JSON object.

        Notes
        -----
        Same contract as `clean_gpp_observation_overrides`: produced and
        validated server-side by `serialize_template_overrides`, so this only
        guards a malformed or hand-edited post.
        """
        return self._clean_json_object(
            "gpp_target_overrides", "the template target settings"
        )

    def _clean_json_object(self, field: str, description: str) -> dict:
        """Parse a hidden JSON-object field.

        Parameters
        ----------
        field : str
            The cleaned-data key to read.
        description : str
            Human-readable name for the error message.

        Returns
        -------
        dict
            The parsed object, or ``{}`` when blank.

        Raises
        ------
        `forms.ValidationError`
            If the value is not a JSON object.
        """
        import json  # noqa: PLC0415

        raw = (self.cleaned_data.get(field) or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise forms.ValidationError(
                f"Could not read {description}."
            ) from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError(
                f"{description.capitalize()} must be a JSON object."
            )
        return parsed

    def clean_gpp_observation_overrides(self):
        """Parse the overrides posted by the template panel.

        Returns
        -------
        dict
            The override properties, or ``{}`` if none were set.

        Raises
        ------
        `forms.ValidationError`
            If the value is not a JSON object.

        Notes
        -----
        Carried as a hidden JSON string because it is produced by the panel's
        observation editor rather than typed. Already validated server-side by
        `serialize_template_overrides` before reaching here, so this only
        guards against a malformed or hand-edited post.
        """
        import json  # noqa: PLC0415

        raw = (self.cleaned_data.get("gpp_observation_overrides") or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise forms.ValidationError(
                "Could not read the template overrides."
            ) from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError(
                "Template overrides must be a JSON object."
            )
        return parsed

    def clean(self):
        """Require a template when automatic triggering is enabled.

        Notes
        -----
        Both rules live here rather than on individual fields, because each
        depends on another field: they only apply when
        `trigger_gemini_observations` is ticked.

        The two are handled differently on purpose. Auto-save is *implied* --
        triggering needs a target, and nobody wants one without the other, so
        refusing the submission would be pedantry. A missing template is a
        real error: GOATS cannot invent one, and without it every alert would
        be skipped for a reason only visible in the trigger records.
        """
        cleaned = super().clean()

        if cleaned.get("trigger_gemini_observations"):
            # Auto-save is implied, not required. Triggering needs a target to
            # point the new observation at, and turning it on without saving
            # was previously rejected as an error -- but the two are not really
            # a choice: nobody wants triggering *without* the target it
            # depends on. Enabling it silently is friendlier than refusing the
            # submission, and the checkbox is ticked in the browser too so the
            # change is visible rather than surprising.
            cleaned["save_all_targets"] = True

            if not cleaned.get("gpp_observation_id"):
                self.add_error(
                    "trigger_gemini_observations",
                    "Select a GPP template observation to clone before "
                    "enabling automatic triggering.",
                )
            elif not (
                cleaned.get("gpp_target_id") and cleaned.get("gpp_instrument")
            ):
                # Selecting a template is not the same as applying it. Apply
                # is what captures the target -- and with it the SED, which an
                # ANTARES alert cannot supply -- and the instrument needed to
                # record the observation in GOATS.
                #
                # Both used to be optional, so a half-configured template
                # passed validation and then degraded silently at trigger
                # time: targets with an empty source profile, observations
                # that never appeared in GOATS, and nothing anywhere saying
                # why. Failing here is the only point at which the PI can see
                # the problem.
                self.add_error(
                    "trigger_gemini_observations",
                    "Apply the template settings before enabling automatic "
                    "triggering: choosing an observation is not enough, since "
                    "Apply is what captures its source profile and "
                    "instrument.",
                )

        return cleaned

    def clean_handler_code(self) -> str:
        """Validate handler code at submit time: structure AND an actual
        dry run against a realistic test locus (see
        `goats_tom.antares_locus_handler.validate_handler_code`), so most
        bugs -- including ones that only show up when the code actually
        runs, like returning an int instead of a bool -- are caught here
        rather than only failing later inside the live consumer loop.

        Returns
        -------
        str
            The handler code, unchanged (validation only) -- including
            when it's effectively blank (e.g. fully commented out), so
            the user's original text is preserved for later editing
            rather than silently cleared.

        Raises
        ------
        forms.ValidationError
            If the code contains a disallowed pattern, fails to compile,
            doesn't define `myfilter`, or raises/returns the wrong type
            when actually run against a test locus. Not raised if the
            code is effectively blank (empty, whitespace, or
            comments-only) -- that's treated the same as leaving the
            field empty, not as an error, since a fully commented-out
            handler is a common, intentional way to temporarily disable
            it without deleting the code.
        """
        source = self.cleaned_data.get("handler_code", "")

        # The checkbox is the only thing that decides whether a handler is in
        # use. Nothing about the text itself is inspected for intent.
        #
        # An earlier version compared the text against the pre-filled skeleton
        # and discarded an exact match. That was too fragile to rely on: the
        # editor is pre-filled, so typing a single stray space -- or the
        # editor normalising a line ending -- made it "edited", and the user
        # silently acquired a handler they never wrote. An explicit tick
        # cannot be given by accident.
        #
        # Returning "" rather than the source when unticked means an unused
        # handler is not stored, so `is_active_handler_code` on the status
        # banner and the consumer's own checks all agree without needing a
        # separate "enabled" flag on the subscription.
        if not self.cleaned_data.get("use_handler_code"):
            return ""

        if is_effectively_blank(source):
            return source

        try:
            validate_handler_code(
                source, user=self.user
            )
        except LocusHandlerError as exc:
            raise forms.ValidationError(str(exc)) from exc

        return source
