__all__ = ["UsernamePasswordLoginForm"]

from django import forms


class UsernamePasswordLoginForm(forms.Form):
    """A form to input login information.

    Attributes
    ----------
    username : `forms.CharField`
        The field for the username.
    password : `forms.CharField`
        The field for the password.
    """

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True,
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )
