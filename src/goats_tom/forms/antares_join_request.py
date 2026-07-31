"""Form for requesting access to a PI's ANTARES dashboard."""

__all__ = ["AntaresJoinRequestForm"]

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from goats_tom.antares_membership import requestable_pi_groups


class AntaresJoinRequestForm(forms.Form):
    """Asks which PI group to join, and what access to request.

    Attributes
    ----------
    pi_group : `forms.ModelChoiceField`
        The group to request. The queryset is built per-instance from
        `goats_tom.antares_membership.requestable_pi_groups`, so groups the
        user owns, already belongs to, or already has a pending request for
        are never offered -- a choice that cannot succeed shouldn't be
        selectable.
    request_save_targets : `forms.BooleanField`
        Whether to also ask for permission to save loci as targets. Viewing
        is implied by requesting at all and so isn't a separate field. What
        is actually granted remains the PI's decision, which is why this is
        worded as a request rather than a setting.
    message : `forms.CharField`
        Optional note to the PI. A PI receiving a request from an unfamiliar
        username otherwise has nothing to base a decision on, so this is
        where a programme or collaboration is explained.

    """

    pi_group = forms.ModelChoiceField(
        queryset=None,
        label="PI group",
        empty_label="Select a group",
        help_text="The PI whose ANTARES dashboard you want access to.",
    )
    request_save_targets = forms.BooleanField(
        label="Also request permission to save loci as targets",
        required=False,
        help_text=(
            "Leave unchecked to request view-only access. The PI decides "
            "what to grant."
        ),
    )
    message = forms.CharField(
        label="Message to the PI (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "e.g. which programme or collaboration you're working on."
                ),
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        """Build the form, restricting group choices to what `user` may request.

        Parameters
        ----------
        user : `django.contrib.auth.models.User`, optional
            The requesting user. Required in practice -- without it the
            group queryset is empty, so the form cannot validate. Passed
            explicitly rather than read from a thread-local request so the
            form is testable in isolation.
        """
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["pi_group"].queryset = requestable_pi_groups(user)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Request access"))
