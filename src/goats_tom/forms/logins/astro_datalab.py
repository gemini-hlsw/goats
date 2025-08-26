__all__ = ["AstroDatalabLoginForm"]

from django import forms

from goats_tom.models import AstroDatalabLogin


class AstroDatalabLoginForm(forms.ModelForm):
    """Form to input username and password for Astro Datalab."""

    class Meta:
        model = AstroDatalabLogin
        fields = ["username", "password"]
        labels = {"username": "Username", "password": "Password"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
        }
