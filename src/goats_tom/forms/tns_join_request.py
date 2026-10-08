"""Forms for requesting and configuring shared TNS group access."""

__all__ = [
    "TNSJoinRequestForm",
    "TNSGroupSettingsForm",
    "TNSGroupSettingsFormSet",
]

from django import forms
from django.forms import modelformset_factory

from goats_tom.models import TNSGroup
from goats_tom.tns_membership import requestable_groups


class TNSJoinRequestForm(forms.Form):
    """Asks which TNS group to request posting access to.

    Attributes
    ----------
    tns_group : `forms.ModelChoiceField`
        The group to request. Scoped per-instance by
        `goats_tom.tns_membership.requestable_groups`.
    message : `forms.CharField`
        Optional note to the owner, who is deciding whether an unfamiliar
        username may post under their bot's name. Capped at 500 characters.

    Notes
    -----
    No "what to request" field: there is one permission, so a checkbox
    would offer a choice that does not exist.
    """

    tns_group = forms.ModelChoiceField(
        queryset=TNSGroup.objects.none(),
        label="TNS group open to new members",
        empty_label="Select a group",
        help_text="The group you want to report or classify under.",
    )
    message = forms.CharField(
        label="Message to the owner (optional)",
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
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
        self.fields["tns_group"].label_from_instance = lambda group: (
            f"{group.name} (owner: {group.owner.username})"
        )


class TNSGroupSettingsForm(forms.ModelForm):
    """One TNS group the owner's bot may file under, and how it is shared.

    Attributes
    ----------
    name : `forms.CharField`
        The group name, spelled as it is on TNS. Editable, which is the
        point of holding groups as rows: correcting it keeps every approved
        member, where retyping a name in a list revoked them all.
    allow_join_requests : `forms.BooleanField`
        Whether other users may ask to post through this group.
    recommended_authors : `forms.CharField`
        Author list pre-filled on posts made through this group. Free text,
        matching what TNS accepts, and editable before sending.

    Notes
    -----
    The labels are short because they are rendered as the column headings of
    one row per group, and carry no help text for the same reason: repeating
    two sentences beside every row said the same thing as many times as the
    user had groups. The page states them once above the table.
    """

    class Meta:
        model = TNSGroup
        fields = ["name", "allow_join_requests", "recommended_authors"]
        # Short: each label is a column heading over one control.
        labels = {
            "name": "Group",
            "allow_join_requests": "Open",
            "recommended_authors": "Recommended co-authors",
        }
        widgets = {
            # Rendered as a Bootstrap switch, which reads as the on/off
            # setting it is rather than as one more tick box in a form.
            "allow_join_requests": forms.CheckboxInput(attrs={"role": "switch"}),
            # One row, so every control in the line is the same height.
            "recommended_authors": forms.Textarea(
                attrs={
                    "rows": 1,
                    "placeholder": (
                        "e.g. A. Author (Institution), B. Author (Institution)"
                    ),
                }
            ),
        }


class BaseTNSGroupSettingsFormSet(forms.BaseModelFormSet):
    """The owner's groups as one editable table."""

    def add_fields(self, form, index) -> None:
        """Mark the trailing blank row as the one that adds a group.

        Parameters
        ----------
        form : `TNSGroupSettingsForm`
            The row being built.
        index : int or None
            Its position, or `None` for the empty form the page clones.

        Notes
        -----
        Set here rather than in the template, where the placeholder would
        have to be attached by guessing which row is the extra one. An empty
        input at the end of a table otherwise reads as a rendering fault
        rather than as an invitation.
        """
        super().add_fields(form, index)
        # `None` is the template's empty form, which the page clones to add
        # a row, so it carries the placeholder too.
        if index is None or index >= self.initial_form_count():
            form.fields["name"].widget.attrs["placeholder"] = "Add a group"

    def clean(self) -> None:
        """Reject two rows naming the same group.

        Notes
        -----
        The model's unique constraint is on ``(owner, name)``, and `owner` is
        not a field here, so `ModelForm` cannot check it on its own. Every
        row the owner has is in this formset, so comparing within it is the
        whole comparison.

        Case-insensitively: TNS treats the name as one group however it is
        typed, and two rows differing only in case would split its settings
        and its members in two.
        """
        super().clean()
        if any(self.errors):
            return

        seen = set()
        for form in self.forms:
            if self._should_delete_form(form):
                continue
            name = (form.cleaned_data.get("name") or "").strip()
            if not name:
                continue
            if name.casefold() in seen:
                form.add_error("name", f"'{name}' is listed twice.")
            seen.add(name.casefold())


# `extra=0`: the page's Add button clones `empty_form` when a row is wanted,
# and `can_delete` lets the list shrink as well as grow.
TNSGroupSettingsFormSet = modelformset_factory(
    TNSGroup,
    form=TNSGroupSettingsForm,
    formset=BaseTNSGroupSettingsFormSet,
    extra=0,
    can_delete=True,
)
