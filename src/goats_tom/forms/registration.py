"""Self-registration form for new GOATS accounts."""

__all__ = ["RegistrationForm"]

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.models import Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from goats_tom.forms.user import selectable_groups


class RegistrationForm(UserCreationForm):
    """Public sign-up form. The account is created but cannot sign in yet.

    Deliberately a plain `UserCreationForm` rather than TOM's
    ``CustomUserCreationForm``: that one exposes a ``groups`` field, which an
    unapproved stranger must not be able to set for themselves. Group
    membership is an administrator's decision after approval.

    Attributes
    ----------
    email : `forms.EmailField`
        Required, so an administrator has some way to identify and contact the
        applicant.
    affiliation : `forms.CharField`
        Required. The applicant's institution. Stored on TOM Toolkit's
        `tom_common.models.Profile`, which already has this field, rather
        than on the registration request -- so it stays with the account
        after approval instead of being stranded on a decided request.
    requested_groups : `forms.ModelMultipleChoiceField`
        Groups the applicant would like to join. Optional. Offers the same
        list an administrator sees when creating a user (see
        `goats_tom.forms.user.selectable_groups`), so automatically-managed
        groups stay hidden.

        Recorded as a *request*, not applied. This form is public, so treating
        the selection as an assignment would let anyone grant themselves
        access to whatever a group shares, effective the moment they were
        approved.
    reason : `forms.CharField`
        Optional note about which programme or collaboration they are with.
        An administrator approving an unfamiliar username otherwise has
        nothing to judge by.

    """

    email = forms.EmailField(
        required=True,
        help_text="Used to identify you. Required.",
    )
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    affiliation = forms.CharField(
        max_length=100,
        required=True,
        help_text="Your institution or organisation. Required.",
    )
    requested_groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Groups you'd like to join (optional)",
        help_text=(
            "An administrator decides what to grant. Leave blank if you're "
            "not sure."
        ),
    )
    reason = forms.CharField(
        label="Why do you need access? (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "e.g. the programme or collaboration you're working with, "
                    "and who can vouch for you."
                ),
            }
        ),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    # Identity first, then credentials, then the optional note. Django
    # appends explicitly-declared fields after the model's own, which would
    # otherwise strand "affiliation" below the two password boxes -- an odd
    # place to be asked who you work for.
    field_order = [
        "username",
        "first_name",
        "last_name",
        "email",
        "affiliation",
        "password1",
        "password2",
        "requested_groups",
        "reason",
    ]

    def __init__(self, *args, **kwargs):
        """Build the form with a submit button."""
        super().__init__(*args, **kwargs)
        # Set per-instance rather than at class definition, so the list
        # reflects the groups that exist now rather than at import time.
        self.fields["requested_groups"].queryset = selectable_groups()
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Request an account"))

    def clean_email(self):
        """Reject an address already in use.

        Returns
        -------
        str
            The cleaned email address.

        Raises
        ------
        `forms.ValidationError`
            If another account already uses this address.

        Notes
        -----
        Django does not enforce email uniqueness on `User`. Allowing
        duplicates here would let somebody register a second account under a
        colleague's address, which an administrator scanning the queue could
        easily wave through.
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )
        return email

    def save(self, commit=True):
        """Create the account in an inactive state, with its profile.

        Returns
        -------
        `User`
            The new, inactive user.

        Notes
        -----
        ``is_active = False`` is what makes this safe: Django's authentication
        backend refuses to sign in an inactive user, so the account does
        nothing until an administrator approves it. Creating the row up front
        (rather than only storing the request) reserves the username and lets
        the applicant choose their own password, instead of one being
        generated and sent to them -- which would need working email.

        The affiliation is written to `tom_common.models.Profile`, which TOM
        creates for every user. `update_or_create` rather than `create`,
        because TOM's own signals may already have made the profile by the
        time this runs -- creating a second would raise on the one-to-one
        constraint.
        """
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
            self._save_affiliation(user)
        return user

    def _save_affiliation(self, user) -> None:
        """Store the affiliation on the user's TOM profile.

        Parameters
        ----------
        user : `User`
            The newly-created account.
        """
        from tom_common.models import Profile  # noqa: PLC0415

        Profile.objects.update_or_create(
            user=user,
            defaults={"affiliation": self.cleaned_data["affiliation"]},
        )
