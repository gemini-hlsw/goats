"""Form for subscribing to ANTARES Kafka stream topics."""

__all__ = ["AntaresStreamSubscribeForm"]

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
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
            attrs={"placeholder": "extragalactic_staging, nuclear_transient_staging"}
        ),
        help_text=mark_safe(
            "One or more ANTARES Kafka topic names, separated by commas. "
            'Refer <a href="https://nsf-noirlab.gitlab.io/csdc/antares/'
            'devkit/reference/filters/" target="_blank" '
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
            "Only applies to loci ingested after this is enabled -- it "
            "does not retroactively save loci already in the dashboard."
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
                    "    # numpy, pandas, astropy, and astroquery are already\n"
                    "    # available by name. Importing is not allowed.\n"
                    "    mag = locus.properties.get(\"newest_alert_magnitude\") or 99\n"
                    "    bright_enough = bool(numpy.all(numpy.array([mag]) < 19))\n"
                    "\n"
                    "    coord = astropy.coordinates.SkyCoord(\n"
                    "        ra=locus.ra, dec=locus.dec, unit=\"deg\"\n"
                    "    )\n"
                    "    away_from_plane = abs(coord.galactic.b.degree) > 10\n"
                    "\n"
                    "    return bright_enough and away_from_plane"
                ),
            }
        ),
        help_text=mark_safe(
            "Optional. Define <code>myfilter(locus)</code> returning "
            "True (keep) or False (skip). numpy, pandas, astropy, and "
            "astroquery are available by name -- no 'import' (blocked, "
            "along with file/network access, eval/exec). See "
            '<a href="https://nsf-noirlab.gitlab.io/csdc/antares/client/'
            'api.html#antares_client.models.Locus" target="_blank" '
            'rel="noopener noreferrer">the Locus API</a> for available '
            "attributes. Leave blank to keep every locus."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Start ingesting"))
        # Errors are shown via a unified banner in the template (the same
        # one used for runtime handler failures), not crispy's default
        # inline per-field rendering -- avoids showing the same error
        # twice in two different visual styles.
        self.helper.form_show_errors = False

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
            validate_handler_code(source)
        except LocusHandlerError as exc:
            raise forms.ValidationError(str(exc)) from exc

        return source
