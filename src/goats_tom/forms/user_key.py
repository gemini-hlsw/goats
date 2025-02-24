__all__ = ["UserKeyForm"]

from django import forms

from goats_tom.models import UserKey


class UserKeyForm(forms.ModelForm):
    class Meta:
        model = UserKey
        fields = ["email", "site", "password"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "site": forms.Select(attrs={"class": "form-control"}),
            "password": forms.PasswordInput(attrs={"class": "form-control"}),
        }
