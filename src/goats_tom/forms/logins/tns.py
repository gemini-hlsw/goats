__all__ = ["TNSLoginForm"]

from django import forms

from goats_tom.models import TNSLogin


class TNSLoginForm(forms.ModelForm):
    """Form for managing TNS login credentials."""

    group_names = forms.CharField(
        label="Group Names",
        help_text="Enter one group name per line.",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    class Meta:
        model = TNSLogin
        fields = ["token", "bot_id", "bot_name", "group_names"]
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

    def clean_group_names(self):
        data = self.cleaned_data["group_names"]
        return [line.strip() for line in data.splitlines() if line.strip()]
