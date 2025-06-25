__all__ = ["TokenLoginForm"]

from django import forms


class TokenLoginForm(forms.Form):
    """A form to input token information.

    Attributes
    ----------
    token : forms.CharField
        The field for the token.
    """

    token = forms.CharField(
        label="Token",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )
