__all__ = ["GOALoginForm"]

from django import forms

from goats_tom.models import GOALogin


class GOALoginForm(forms.ModelForm):
    """Form to input username and password for GOA."""

    class Meta:
        model = GOALogin
        fields = ["username", "password"]
        labels = {"username": "Username", "password": "Password"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
        }
