__all__ = ["LCOLoginForm"]

from django import forms

from goats_tom.models import LCOLogin


class LCOLoginForm(forms.ModelForm):
    """Form to input a token for LCO and SOAR."""

    class Meta:
        model = LCOLogin
        fields = ["token"]
        labels = {"token": "API Token"}
        widgets = {
            "token": forms.PasswordInput(attrs={"class": "form-control"}),
        }
