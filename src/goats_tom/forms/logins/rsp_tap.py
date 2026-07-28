__all__ = ["RSPTapLoginForm"]

from django import forms
from django.utils.safestring import mark_safe

from goats_tom.models import RSPTapLogin


class RSPTapLoginForm(forms.ModelForm):
    """Form for managing Rubin Science Platform (RSP) TAP access tokens.

    Notes
    -----
    Any logged-in user may store their own token here (no superuser
    restriction) -- unlike ANTARES Kafka credentials, an RSP token is a
    personal, per-researcher credential, not shared infrastructure. See
    https://rsp.lsst.io/guides/auth/creating-user-tokens.html for how to
    create one.
    """

    class Meta:
        model = RSPTapLogin
        fields = ["access_token"]
        labels = {
            "access_token": "RSP Access Token",
        }
        widgets = {
            "access_token": forms.PasswordInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "access_token": mark_safe(
                "Used to query Rubin catalog data (via the TAP service) "
                "from custom ANTARES locus handler code. See "
                '<a href="https://rsp.lsst.io/guides/auth/'
                'creating-user-tokens.html" target="_blank" '
                'rel="noopener noreferrer">Creating user tokens</a> for '
                "how to create one."
            ),
        }
