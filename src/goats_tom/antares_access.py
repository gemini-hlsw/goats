"""Access control for ANTARES locus dashboards.

One place that answers "which dashboard may this user see, and what may
they do on it". Every dashboard view goes through these rather than
querying memberships directly, so there is a single definition of access to
audit and change.

The model is:

- A **PI** owns a subscription (`AntaresStreamSubscription.owner`) and may
  do everything on their own dashboard, including configuring and clearing
  it. Their access follows from ownership and is never stored as a
  membership row, so it cannot be revoked by accident.
- A **member** has been approved into the PI's group and holds up to two
  permissions on `AntaresDashboardMembership`: view the dashboard, and save
  loci from it as targets. Members never configure, stop, or clear a
  subscription -- those remain the PI's alone.
- A **superuser** may view any dashboard, matching how the rest of GOATS
  treats superusers (see `tom_targets.permissions.targets_for_user`, which
  bypasses filtering for them entirely). Deliberately *not* extended to
  saving or clearing: those write data attributed to a user, and doing them
  implicitly on a PI's behalf would misattribute the result.
"""

__all__ = [
    "accessible_subscriptions",
    "get_subscription_for_view",
    "can_view_dashboard",
    "can_save_targets",
    "can_configure",
    "membership_for",
]

from django.db.models import Q

from goats_tom.models import AntaresDashboardMembership, AntaresStreamSubscription


def membership_for(user, subscription):
    """Return `user`'s membership row for `subscription`'s group, or `None`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to look up.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription whose owning PI group to check membership of.

    Returns
    -------
    `goats_tom.models.AntaresDashboardMembership` or None
        The membership row, or `None` if the user is not a member, if the
        subscription has no owner, or if the owner has no PI group yet.

    Notes
    -----
    Returns `None` for the PI themselves: owners are not members of their
    own group in this table (see the module docstring), so callers must
    check ownership separately -- which `can_view_dashboard` and friends
    already do.
    """
    if user is None or not user.is_authenticated or subscription is None:
        return None
    if subscription.owner_id is None:
        return None
    return (
        AntaresDashboardMembership.objects.filter(
            user=user, pi_group__pi_id=subscription.owner_id
        )
        .select_related("pi_group")
        .first()
    )


def accessible_subscriptions(user):
    """All subscriptions whose dashboards `user` may view.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to scope by.

    Returns
    -------
    `django.db.models.QuerySet`
        Subscriptions the user owns, plus those belonging to PI groups they
        hold `can_view_dashboard` in. Empty for anonymous users.

    Notes
    -----
    A queryset rather than a list, so callers can filter and paginate it
    further without loading every row. `distinct()` because a user could in
    principle match on both branches of the `Q` -- they shouldn't, since
    owners aren't members of their own group, but relying on that here
    would make a data anomaly silently duplicate rows in a listing.
    """
    if user is None or not user.is_authenticated:
        return AntaresStreamSubscription.objects.none()

    if user.is_superuser:
        return AntaresStreamSubscription.objects.all()

    return AntaresStreamSubscription.objects.filter(
        Q(owner=user)
        | Q(
            owner__antares_pi_group__memberships__user=user,
            owner__antares_pi_group__memberships__can_view_dashboard=True,
        )
    ).distinct()


def get_subscription_for_view(user, subscription_id=None):
    """Resolve which dashboard to show `user`, or `None` if they have none.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The requesting user.
    subscription_id : int, optional
        An explicitly requested subscription (e.g. from the URL, when a
        member has access to more than one PI's dashboard). If given and
        the user may not view it, `None` is returned -- the caller renders
        an empty dashboard or a 404 rather than falling back to a dashboard
        they *can* see, which would silently show the wrong data.

    Returns
    -------
    `goats_tom.models.AntaresStreamSubscription` or None
        The subscription to render, or `None`.

    Notes
    -----
    With no `subscription_id`, a user's own subscription wins over any they
    are a member of. A PI who is also a member of someone else's group
    should land on their own dashboard by default.
    """
    if user is None or not user.is_authenticated:
        return None

    if subscription_id is not None:
        return accessible_subscriptions(user).filter(pk=subscription_id).first()

    own = AntaresStreamSubscription.objects.filter(owner=user).first()
    if own is not None:
        return own

    return accessible_subscriptions(user).first()


def can_view_dashboard(user, subscription) -> bool:
    """Whether `user` may view `subscription`'s dashboard.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to check.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The dashboard's subscription.

    Returns
    -------
    bool
        `True` for the owner, for a superuser, and for a member holding
        `can_view_dashboard`.
    """
    if user is None or not user.is_authenticated or subscription is None:
        return False
    if subscription.owner_id == user.pk or user.is_superuser:
        return True
    membership = membership_for(user, subscription)
    return membership is not None and membership.can_view_dashboard


def can_save_targets(user, subscription) -> bool:
    """Whether `user` may save loci from `subscription`'s dashboard.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to check.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The dashboard's subscription.

    Returns
    -------
    bool
        `True` for the owner, and for a member holding *both*
        `can_view_dashboard` and `can_save_targets`.

    Notes
    -----
    Requires view permission as well as save, so revoking a member's view
    access can't leave them able to keep saving from a dashboard they can
    no longer see.

    Superusers are deliberately excluded here, unlike
    `can_view_dashboard`. Saving records the acting user on the target
    (`AntaresTargetSave.saved_by`) and grants them access to it, so an
    admin saving on a PI's behalf would attribute the target to the admin
    and grant it to the wrong person.
    """
    if user is None or not user.is_authenticated or subscription is None:
        return False
    if subscription.owner_id == user.pk:
        return True
    membership = membership_for(user, subscription)
    return (
        membership is not None
        and membership.can_view_dashboard
        and membership.can_save_targets
    )


def can_configure(user, subscription) -> bool:
    """Whether `user` may start, stop, or clear `subscription`.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to check.
    subscription : `goats_tom.models.AntaresStreamSubscription`
        The subscription in question.

    Returns
    -------
    bool
        `True` only for the owner.

    Notes
    -----
    Owner-only, with no membership permission and no superuser bypass.
    These actions consume the owner's own ANTARES credentials and quota,
    change what their whole team sees, and -- in the case of clearing --
    destroy data. There is deliberately no way to delegate them; a PI who
    wants someone else to configure ingestion can share the credentials,
    which is an explicit choice rather than an implicit one.
    """
    if user is None or not user.is_authenticated or subscription is None:
        return False
    return subscription.owner_id == user.pk
