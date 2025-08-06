__all__ = ["GPPLoginForm"]

from django import forms

from goats_tom.models import GPPLogin


class GPPLoginForm(forms.ModelForm):
    """Form to input a token for GPP."""

    class Meta:
        model = GPPLogin
        fields = ["token"]
        labels = {"token": "API Token"}
        widgets = {
            "token": forms.PasswordInput(attrs={"class": "form-control"}),
        }
