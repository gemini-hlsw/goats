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
        # No help text: it repeated the description under the heading
        # almost word for word, and the field is a single token box that
        # needs no explanation of its own.
        help_texts = {"access_token": ""}
