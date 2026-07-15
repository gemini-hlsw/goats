"""Form for subscribing to ANTARES Kafka stream topics."""

__all__ = ["AntaresStreamSubscribeForm"]

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.safestring import mark_safe

from goats_tom.antares_locus_handler import LocusHandlerError, check_handler_source


class AntaresStreamSubscribeForm(forms.Form):
    """Collects a comma-separated topic list, two (currently no-op) radio
    options, and optional custom locus-handler code for the ANTARES Kafka
    stream consumer.

    Attributes
    ----------
    topics : `forms.CharField`
        Comma-separated Kafka topic names, e.g.
        ``"extragalactic_staging, nuclear_transient_staging"``.
    save_all_targets : `forms.ChoiceField`
        Single radio option, unselected by default. Not yet wired to any
        behavior -- selecting it currently does nothing.
    trigger_gemini_observations : `forms.ChoiceField`
        Single radio option, unselected by default. Not yet wired to any
        behavior -- selecting it currently does nothing.
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
        help_text="One or more ANTARES Kafka topic names, separated by commas.",
    )
    save_all_targets = forms.ChoiceField(
        label="",
        choices=[("yes", "Automatically save all ingested loci as targets")],
        required=False,
        initial=None,
        widget=forms.RadioSelect,
        help_text="Not yet active; selecting this currently has no effect.",
    )
    trigger_gemini_observations = forms.ChoiceField(
        label="",
        choices=[("yes", "Automatically trigger Gemini observations")],
        required=False,
        initial=None,
        widget=forms.RadioSelect,
        help_text="Not yet active; selecting this currently has no effect.",
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
                    "    mag = locus.properties.get(\"newest_alert_magnitude\") or 99\n"
                    "    return mag < 18"
                ),
            }
        ),
        help_text=mark_safe(
            "Optional. Define a function named exactly 'myfilter' that "
            "takes 'locus' and returns True (keep) or False (skip), as an "
            "additional filter beyond the topics above. See the ANTARES "
            "Locus API for available attributes/methods: "
            '<a href="https://nsf-noirlab.gitlab.io/csdc/antares/client/'
            'api.html#antares_client.models.Locus" target="_blank" '
            'rel="noopener noreferrer">antares_client.models.Locus</a>. '
            "The numpy, pandas, astropy, and astroquery packages are "
            "available directly (no import statement needed or allowed); "
            "all other imports are blocked, along with file/network "
            "access, eval/exec, and other restricted builtins. Leave "
            "blank to keep every locus on the subscribed topics."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Start ingesting"))

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
        """Validate handler code against the same restrictions used at
        runtime, so obviously-bad code is rejected at submit time rather
        than only failing later inside the live consumer loop.

        Returns
        -------
        str
            The handler code, unchanged (validation only).

        Raises
        ------
        forms.ValidationError
            If the code contains a disallowed pattern or fails to compile.
        """
        source = self.cleaned_data.get("handler_code", "")
        if not source.strip():
            return source

        try:
            check_handler_source(source)
            compile(source, "<antares_locus_handler>", "exec")
        except LocusHandlerError as exc:
            raise forms.ValidationError(str(exc)) from exc
        except SyntaxError as exc:
            raise forms.ValidationError(f"Syntax error: {exc}") from exc

        return source
