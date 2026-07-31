"""User create/update views using the filtered group picker."""

__all__ = ["GOATSUserCreateView", "GOATSUserUpdateView"]

from tom_common.views import UserCreateView, UserUpdateView

from goats_tom.forms import GOATSUserCreationForm


class GOATSUserCreateView(UserCreateView):
    """TOM's user creation view with automatically-managed groups hidden.

    Only the form class differs; every permission check and redirect is
    inherited. See `goats_tom.forms.user.selectable_groups` for what is
    filtered out and why.
    """

    form_class = GOATSUserCreationForm


class GOATSUserUpdateView(UserUpdateView):
    """TOM's user update view with automatically-managed groups hidden.

    Same reasoning as `GOATSUserCreateView`. Notably this is also the view
    where a user's existing groups are displayed, so without the filter an
    administrator would see (and could accidentally untick) the user's own
    personal group -- which the signal would then silently recreate on the
    next save, since a user with no group cannot select one when creating
    observations.
    """

    form_class = GOATSUserCreationForm
