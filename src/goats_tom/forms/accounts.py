"""Forms to request an account, approve one, sign in and reset a password."""

__all__ = [
    "AccountApprovalForm",
    "NewPasswordForm",
    "PasswordResetRequestForm",
    "PasswordResetUsernameForm",
    "RegistrationForm",
    "SignInForm",
]

from typing import Any

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group, User
from django.urls import reverse

from goats_tom.forms.validators import MaxWordsValidator
from goats_tom.models import AccountRequest
from goats_tom.outbox import queue_email, site_url


class RegistrationForm(UserCreationForm):
    """Public form to request an account.

    No groups field: the administrator chooses them when approving.
    """

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    affiliation = forms.CharField(max_length=100)
    message = forms.CharField(
        label="Why do you need access? (optional)",
        required=False,
        validators=[MaxWordsValidator(200)],
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="You can enter up to 200 words.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        # Django's, without its leading "Required.": the asterisk says it.
        help_texts = {
            "username": "150 characters or fewer. Letters, digits and @/./+/-/_ only."
        }

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


class PasswordResetRequestForm(PasswordResetForm):
    """Django's password reset form, emailing through the GOATS outbox."""

    def send_mail(
        self,
        subject_template_name: str,
        email_template_name: str,
        context: dict[str, Any],
        from_email: str | None,
        to_email: str,
        html_email_template_name: str | None = None,
    ) -> None:
        """Queue the reset link for `to_email`.

        Parameters
        ----------
        subject_template_name, email_template_name : str
            Unused: GOATS renders its own templates.
        context : dict[str, Any]
            Django's context, with ``uid``, ``token``, ``user``, ``protocol``
            and ``domain``.
        from_email : str or None
            Unused: the outbox sends from ``DEFAULT_FROM_EMAIL``.
        to_email : str
            The account's address.
        html_email_template_name : str, optional
            Unused.
        """
        path = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": context["uid"], "token": context["token"]},
        )
        # Without GOATS_SITE_URL, the host the request came in on.
        reset_url = (
            site_url(path) or f"{context['protocol']}://{context['domain']}{path}"
        )
        queue_email(
            to_email,
            "Reset your GOATS password",
            "registration/emails/password_reset",
            {"user": context["user"], "reset_url": reset_url},
        )


class PasswordResetUsernameForm(forms.Form):
    """The account whose password an administrator should reset."""

    username = forms.CharField(max_length=150)


class NewPasswordForm(SetPasswordForm):
    """Replace a temporary password with one the user chooses."""

    def clean(self) -> dict[str, Any]:
        """Reject keeping the temporary password.

        Returns
        -------
        dict[str, Any]
            The cleaned data.
        """
        cleaned_data = super().clean()
        if self.user.check_password(cleaned_data.get("new_password1", "")):
            self.add_error(
                "new_password1", "Choose a password other than the temporary one."
            )
        return cleaned_data
