__all__ = ["TNSLoginForm"]

from django import forms

from goats_tom.models import TNSLogin


class TNSLoginForm(forms.ModelForm):
    """Form for managing TNS login credentials.

    Notes
    -----
    No group names: they used to be typed here one per line, which made the
    text the only thing identifying a group, so correcting a typo revoked
    everyone approved for the old spelling. They are rows now, edited in the
    table on the same page -- see `goats_tom.forms.TNSGroupSettingsForm`.
    """

    class Meta:
        model = TNSLogin
        fields = ["token", "bot_id", "bot_name"]
        labels = {
            "token": "API Token",
            "bot_id": "Bot ID",
            "bot_name": "Bot Name",
        }
        widgets = {
            "token": forms.PasswordInput(attrs={"class": "form-control"}),
            "bot_id": forms.TextInput(attrs={"class": "form-control"}),
            "bot_name": forms.TextInput(attrs={"class": "form-control"}),
        }
