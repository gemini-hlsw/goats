"""User creation/update form with a filtered group picker."""

__all__ = ["GOATSUserCreationForm", "selectable_groups"]

from django.contrib.auth.models import Group
from tom_common.forms import CustomUserCreationForm


def selectable_groups():
    """Groups a person should be able to assign somebody to by hand.

    Returns
    -------
    `django.db.models.QuerySet`
        All groups except automatically-managed ones.

    Notes
    -----
    Excludes two kinds of group that GOATS creates on the user's behalf, and
    which are meaningless as manual choices:

    - Personal groups (`goats_tom.models.PersonalGroup`). Every account gets
      exactly one, automatically; ticking somebody else's makes no sense, and
      the list is as long as the user table. This also removes the
      ``user-AnonymousUser`` entry, which existed because django-guardian
      keeps its anonymous placeholder in ``auth_user`` and it was given a
      personal group like any other row.
    - ANTARES PI groups (`goats_tom.models.AntaresPIGroup`). Membership of
      these is granted by the PI approving a request (see
      `goats_tom.antares_membership`), which also records the two dashboard
      permissions. Adding somebody here would put them in the auth group
      without those permissions -- half a membership, and confusing to debug.

    Excluded by *relation*, not by matching a name prefix: a real group that
    happened to be called ``user-something`` would otherwise disappear from
    the picker for no reason.
    """
    return Group.objects.filter(
        personal_group__isnull=True, antares_pi_group__isnull=True
    ).order_by("name")


class GOATSUserCreationForm(CustomUserCreationForm):
    """TOM's user form with automatically-managed groups filtered out.

    TOM's own form offers ``Group.objects.all()``. See `selectable_groups`
    for why that is too much.
    """

    def __init__(self, *args, **kwargs):
        """Build the form and narrow the group choices."""
        super().__init__(*args, **kwargs)
        if "groups" in self.fields:
            self.fields["groups"].queryset = selectable_groups()
