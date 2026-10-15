"""Forms to request an account, approve one and sign in."""

__all__ = [
    "AccountApprovalForm",
    "RegistrationForm",
    "SignInForm",
]


from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group, User

from goats_tom.models import AccountRequest


class RegistrationForm(UserCreationForm):
    """Public form to request an account.

    No groups field: the administrator chooses them when approving.
    """

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    affiliation = forms.CharField(
        max_length=100, help_text="Your institution or organisation."
    )
    message = forms.CharField(
        label="Why do you need access? (optional)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="For example, the programme or collaboration you work with.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    field_order = [
        "username",
        "first_name",
        "last_name",
        "email",
        "affiliation",
        "password1",
        "password2",
        "message",
    ]

    def clean_email(self) -> str:
        """Reject an address another account already uses.

        Returns
        -------
        str
            The address.
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )
        return email


class AccountApprovalForm(forms.Form):
    """The groups an administrator adds an account to when approving it."""

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by("name"), required=False
    )


class SignInForm(AuthenticationForm):
    """Sign-in form that tells an applicant their account awaits approval."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "pending": "Your account is awaiting approval by an administrator.",
    }

    def get_invalid_login_error(self) -> forms.ValidationError:
        """Return the error for a failed sign-in.

        Returns
        -------
        `forms.ValidationError`
            "Pending" for an applicant who gave the right password, so a wrong
            one never reveals that the username exists.
        """
        user = User.objects.filter(
            username=self.cleaned_data.get("username"),
            is_active=False,
            account_request__status=AccountRequest.STATUS_PENDING,
        ).first()
        if user and user.check_password(self.cleaned_data.get("password")):
            return forms.ValidationError(self.error_messages["pending"], code="pending")
        return super().get_invalid_login_error()
