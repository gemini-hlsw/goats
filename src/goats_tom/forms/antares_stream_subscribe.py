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


class AntaresStreamSubscribeForm(forms.Form):
    """Collects a comma-separated topic list, two toggleable checkbox
    options (one now operational, one still a no-op), and optional custom
    locus-handler code for the ANTARES Kafka stream consumer.

    Attributes
    ----------
    topics : `forms.CharField`
        Comma-separated Kafka topic names, e.g.
        ``"extragalactic_staging, nuclear_transient_staging"``.
    group : `forms.CharField`
        Optional Kafka consumer group name. Set here (not in the
        Credential Manager) since it changes far more often than the API
        credentials -- e.g. to force a full replay via a brand-new group.
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
    group = forms.CharField(
        label="Kafka group (optional)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "goats-antares-locus-dashboard"}),
        help_text=(
            "Optional; defaults to a built-in group name if blank. Keeps "
            "offset tracking stable across restarts. Use a new group "
            "name to replay from the earliest available message."
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
        help_text="Not yet active; checking this currently has no effect.",
    )
    handler_code = forms.CharField(
        label="Custom locus handler (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "id": "id_handler_code",
                "rows": 14,
                "class": "font-monospace antares-handler-code-raw",
                "spellcheck": "false",
                "placeholder": (
                    "def myfilter(locus):\n"
                    "    # Return True to keep this locus, False to skip it.\n"
                    "    # Available by name (no 'import'): numpy, pandas,\n"
                    "    # astropy, astroquery, dashboard_locus_count(),\n"
                    "    # RSP_tap_service.\n"
                    "    mag = locus.properties.get(\"newest_alert_magnitude\") or 99\n"
                    "    if mag > 19:\n"
                    "        return False\n"
                    "\n"
                    "    if RSP_tap_service is not None:\n"
                    "        radius = 1.0 / 3600.0\n"
                    "        query = (\n"
                    "            \"SELECT objectId, refExtendedness FROM dp1.Object \"\n"
                    "            \"WHERE CONTAINS(POINT('ICRS', coord_ra, coord_dec), \"\n"
                    "            f\"CIRCLE('ICRS', {locus.ra}, {locus.dec}, {radius})) = 1\"\n"
                    "        )\n"
                    "        table = RSP_tap_service.run_async(query).to_table()\n"
                    "        if len(table) > 0 and table[\"refExtendedness\"][0] >= 0.5:\n"
                    "            return False\n"
                    "\n"
                    "    return True"
                ),
            }
        ),
        help_text=mark_safe(
            "Optional. Define <code>myfilter(locus)</code> returning "
            "True (keep) or False (skip). See "
            '<a href="https://nsf-noirlab.gitlab.io/csdc/antares/client/'
            'api.html#antares_client.models.Locus" target="_blank" '
            'rel="noopener noreferrer">the Locus API</a> for available '
            "attributes. Leave blank to keep every locus. "
            "numpy, pandas, astropy, and astroquery are available by "
            "name. 'import' is not allowed (blocked, along with file "
            "access, eval/exec). "
            "<code>dashboard_locus_count()</code> returns how many loci "
            "are currently on the dashboard, e.g. to stop after N loci: "
            "<code>if dashboard_locus_count() >= 10: return False</code>. "
            "<code>RSP_tap_service</code> (if you've stored an "
            "{rsp_token_link}) queries Rubin catalog data, e.g. "
            "<code>RSP_tap_service.run_async(\"SELECT ...\").to_table()"
            "</code>. See "
            '<a href="https://sdm-schemas.lsst.io/" target="_blank" '
            'rel="noopener noreferrer">here</a> for tables and schemas '
            "for Rubin data products."
        ),
    )

    def __init__(
        self,
        *args,
        available_topics: list[str] | None = None,
        configured_by_user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.available_topics = available_topics or []
        self.configured_by_user = configured_by_user
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Start ingesting"))
        # Errors are shown via a unified banner in the template (the same
        # one used for runtime handler failures), not crispy's default
        # inline per-field rendering -- avoids showing the same error
        # twice in two different visual styles.
        self.helper.form_show_errors = False

        # help_text is defined once, at class-body level, with no access
        # to a specific request/user -- but the RSP token storage link
        # needs a specific user's pk (`user-rsp-tap-login` takes one),
        # which we only have per-instance, from `configured_by_user`
        # (== request.user, passed in by the view). Filled in here,
        # rather than in the static help_text string above, for that
        # reason.
        if self.configured_by_user is not None and self.configured_by_user.pk:
            rsp_token_link = mark_safe(
                '<a href="{}" target="_blank" '
                'rel="noopener noreferrer">RSP access token</a>'.format(
                    reverse(
                        "user-rsp-tap-login", args=[self.configured_by_user.pk]
                    )
                )
            )
        else:
            rsp_token_link = "RSP access token"
        self.fields["handler_code"].help_text = mark_safe(
            self.fields["handler_code"].help_text.format(
                rsp_token_link=rsp_token_link
            )
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
        if is_effectively_blank(source):
            return source

        try:
            validate_handler_code(
                source, configured_by_user=self.configured_by_user
            )
        except LocusHandlerError as exc:
            raise forms.ValidationError(str(exc)) from exc

        return source
