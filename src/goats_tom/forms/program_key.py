__all__ = ["ProgramKeyForm"]

from django import forms

from goats_tom.models import ProgramKey


class ProgramKeyForm(forms.ModelForm):
    class Meta:
        model = ProgramKey
        fields = ["program_id", "site", "password"]
        widgets = {
            "program_id": forms.TextInput(attrs={"class": "form-control"}),
            "site": forms.Select(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
        }
        labels = {"program_id": "Program ID:"}
