"""Forms for requesting and configuring shared TNS group access."""

__all__ = ["TNSJoinRequestForm", "TNSGroupSettingsForm"]

from django import forms

from goats_tom.models import TNSGroup
from goats_tom.tns_membership import requestable_groups


class TNSJoinRequestForm(forms.Form):
    """Asks which TNS group to request posting access to.

    Attributes
    ----------
    tns_group : `forms.ModelChoiceField`
        The group to request. The queryset is built per-instance from
        `goats_tom.tns_membership.requestable_groups`, so groups the user
        owns, already belongs to, that are not accepting requests, or that
        already have a pending request are never offered.
    message : `forms.CharField`
        Optional note to the owner. Approving means letting somebody send
        to a public registry under your bot's name, so an owner facing an
        unfamiliar username needs somewhere for the collaboration or
        programme to be explained.

    Notes
    -----
    Deliberately has no "what to request" field, unlike
    `goats_tom.forms.AntaresJoinRequestForm`. There is one permission --
    post through this group -- so a checkbox would offer a choice that does
    not exist.
    """

    tns_group = forms.ModelChoiceField(
        queryset=TNSGroup.objects.none(),
        label="TNS group",
        empty_label="Select a group",
        help_text="The group you want to report or classify under.",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    message = forms.CharField(
        label="Message to the owner (optional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": (
                    "e.g. the programme or collaboration you're working on"
                ),
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        """Build the form, scoping the group choices to `user`.

        Parameters
        ----------
        user : `django.contrib.auth.models.User`, optional
            The prospective member. Without one the field offers nothing,
            rather than every group on the instance.
        """
        super().__init__(*args, **kwargs)
        self.fields["tns_group"].queryset = requestable_groups(user)
        self.fields["tns_group"].label_from_instance = (
            lambda group: f"{group.name} (owner: {group.owner.username})"
        )


class TNSGroupSettingsForm(forms.ModelForm):
    """The two per-group settings an owner controls.

    Kept separate from `goats_tom.forms.TNSLoginForm` rather than folded
    into it, because the two are answering different questions at different
    times. The credential form takes a free-text list of group names, so a
    group does not exist as a row until that form has been saved -- there
    is nothing to attach a toggle or an author list to until then. Trying
    to collect both in one submission would mean rendering settings for
    groups the user might be about to rename or remove in the same POST.

    Attributes
    ----------
    allow_join_requests : `forms.BooleanField`
        Whether other users may ask to post through this group.
    recommended_authors : `forms.CharField`
        Names pre-filled into the Reporter / Classifier field of posts made
        through this group. Free text, matching what TNS accepts, and a
        recommendation rather than a constraint -- the submitter can still
        edit it on the form, which is the point of pre-filling rather than
        forcing.
    """

    class Meta:
        model = TNSGroup
        fields = ["allow_join_requests", "recommended_authors"]
        labels = {
            "allow_join_requests": (
                "Allow other GOATS users to request access to this group"
            ),
            "recommended_authors": "Recommended co-authors",
        }
        # Deliberately short. These sit directly beneath the control they
        # describe, so they only have to say the one thing the label cannot:
        # that the toggle opens the group to *requests* rather than granting
        # anything, and that an approved user's reports go out under the
        # owner's bot. An introductory paragraph above the controls said the
        # same thing at four times the length and was read by nobody.
        help_texts = {
            "allow_join_requests": (
                "You approve each one. Approved users' reports are sent by "
                "your bot."
            ),
            "recommended_authors": (
                "Added to the author list on reports sent under this group. "
                "Editable before sending."
            ),
        }
        widgets = {
            "allow_join_requests": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "recommended_authors": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": (
                        "e.g. A. Author (Institution), "
                        "B. Author (Institution)"
                    ),
                }
            ),
        }
