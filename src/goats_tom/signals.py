"""Signal handlers for the ANTARES stream feature.

Registered from `goats_tom.apps.GOATSTomConfig.ready`.
"""

__all__ = [
    "create_pi_group_for_kafka_credentials",
    "ensure_user_has_a_group",
]

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from goats_tom.models import AntaresKafkaLogin, AntaresPIGroup

logger = logging.getLogger(__name__)

# Prefix for auto-created PI group names. The name is for humans only --
# `AntaresPIGroup` is what actually links a group to its PI, so nothing
# parses this back apart (see that model's docstring).
PI_GROUP_NAME_PREFIX = "antares"

# Prefix for each user's own personal group. See `ensure_user_has_a_group`.
PERSONAL_GROUP_NAME_PREFIX = "user"


def _unique_group_name(prefix: str, username: str) -> str:
    """Build an unused group name for `username`.

    Parameters
    ----------
    prefix : str
        Namespace for the group, e.g. ``"antares"`` or ``"user"``.
    username : str
        The user's username.

    Returns
    -------
    str
        ``"<prefix>-<username>"``, with ``-2``, ``-3``, ... appended if
        needed to avoid colliding with an existing group.

    Notes
    -----
    A collision is unlikely but entirely possible: `Group.name` is unique
    across all of GOATS, and nothing stops an admin from having already
    created a group by this name for an unrelated purpose. Suffixing keeps
    group creation from failing on an `IntegrityError` in that case. Because
    the PI link lives on `AntaresPIGroup` rather than in the name, a
    suffixed name is purely cosmetic and breaks nothing.
    """
    base = f"{prefix}-{username}"
    if not Group.objects.filter(name=base).exists():
        return base
    suffix = 2
    while Group.objects.filter(name=f"{base}-{suffix}").exists():
        suffix += 1
    return f"{base}-{suffix}"


@receiver(post_save, sender=AntaresKafkaLogin, dispatch_uid="antares_pi_group")
def create_pi_group_for_kafka_credentials(sender, instance, **kwargs) -> None:
    """Give a user a PI group the first time they store Kafka credentials.

    Storing ANTARES Kafka credentials is the point at which a user becomes
    able to run their own stream subscription, so it's also the point at
    which they need a group other users can ask to join (see
    `goats_tom.models.AntaresPIGroup`).

    Parameters
    ----------
    sender : type
        The sending model class (`AntaresKafkaLogin`).
    instance : `goats_tom.models.AntaresKafkaLogin`
        The credential row that was saved.
    **kwargs
        Remaining signal arguments, including `created`.

    Notes
    -----
    Runs on every save, not only on creation, and is idempotent: a user who
    updates their credentials keeps the group they already had, and a user
    whose group was somehow never created (credentials stored before this
    handler existed, or created directly in the admin) gets one on their
    next save. That self-healing is why this isn't gated on `created`.

    The PI is added to their own group as a member. They do not need it for
    dashboard access -- that follows from owning the subscription (see
    `goats_tom.antares_access`) -- but they do need it for target sharing,
    since TOM Toolkit shares targets with `Group` objects and a PI should
    receive anything shared with their own team.

    Failures are logged, never raised. This is a side effect of saving
    credentials, and a group that couldn't be created should not make the
    credential save itself appear to fail -- the credentials are the thing
    the user actually asked to store, and they work without a group. The
    next save retries.
    """
    user = instance.user
    if user is None:
        return

    try:
        with transaction.atomic():
            pi_group = AntaresPIGroup.objects.filter(pi=user).first()
            if pi_group is None:
                group = Group.objects.create(
                    name=_unique_group_name(PI_GROUP_NAME_PREFIX, user.username)
                )
                pi_group = AntaresPIGroup.objects.create(group=group, pi=user)
                logger.info(
                    "Created ANTARES PI group %r for user %s.",
                    group.name,
                    user.username,
                )
            user.groups.add(pi_group.group)
    except Exception:
        logger.exception(
            "Failed to create or join an ANTARES PI group for user %s; "
            "their credentials were still saved.",
            getattr(user, "username", None),
        )


def _is_anonymous_placeholder(user) -> bool:
    """Whether `user` is django-guardian's stand-in anonymous account.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        The user to test.

    Returns
    -------
    bool
        `True` for the row guardian creates to hold permissions granted to
        "anyone".

    Notes
    -----
    guardian stores anonymous permissions against a real row in ``auth_user``,
    so it looks like an ordinary account to any signal watching the user
    model. It is not a person, has no login, and should not appear in group
    pickers -- an earlier version of this module gave it a personal group,
    which then showed up as a selectable "user-AnonymousUser" option.
    """
    name = getattr(settings, "ANONYMOUS_USER_NAME", "AnonymousUser")
    return name is not None and user.username == name


@receiver(
    post_save, sender=get_user_model(), dispatch_uid="personal_group_for_user"
)
def ensure_user_has_a_group(sender, instance, **kwargs) -> None:
    """Give a user their own group if they do not already have one.

    Parameters
    ----------
    sender : type
        The sending model class (the configured user model).
    instance : `django.contrib.auth.models.User`
        The user that was saved.
    **kwargs
        Remaining signal arguments.

    Notes
    -----
    See `goats_tom.models.PersonalGroup` for why every user needs a group at
    all.

    Two details are load-bearing, and both come from a bug where creating a
    user produced an empty ``user-<name>`` group, and that user's first login
    then produced a second group ``user-<name>-2`` holding the actual
    membership.

    First, the membership is added in `transaction.on_commit` rather than
    inline. TOM Toolkit's user form (``tom_common.forms.CustomUserCreationForm``)
    saves in the order ``user.save()`` ... ``self.save_m2m()``, and that
    ``save_m2m`` assigns the form's own ``groups`` field -- which is empty
    when an administrator creates a user without ticking anything. Adding the
    membership inline meant this signal wrote it during ``user.save()`` and
    ``save_m2m`` promptly cleared it, leaving a group with no members.
    Deferring until after commit puts the write after ``save_m2m``, where it
    survives.

    Second, an existing personal group is found through
    `goats_tom.models.PersonalGroup` rather than by name. The name-based
    lookup could not tell "this user already has a group" from "that name is
    taken", so once a membership had been cleared it created a *new*,
    suffixed group instead of rejoining the original.

    Deliberately keyed on "has no personal group" rather than on `created`,
    so accounts predating this handler are repaired on their next save.
    Skips guardian's anonymous placeholder (see `_is_anonymous_placeholder`).

    Failures are logged, never raised: an account must not fail to save
    because a convenience group could not be created.
    """
    from goats_tom.models import PersonalGroup  # noqa: PLC0415

    if instance is None or instance.pk is None:
        return
    if _is_anonymous_placeholder(instance):
        return

    user_pk = instance.pk

    def _ensure() -> None:
        User = get_user_model()
        user = User.objects.filter(pk=user_pk).first()
        if user is None:
            # Deleted between save and commit; nothing to do.
            return
        try:
            with transaction.atomic():
                personal = PersonalGroup.objects.filter(user=user).first()
                if personal is None:
                    group = Group.objects.create(
                        name=_unique_group_name(
                            PERSONAL_GROUP_NAME_PREFIX, user.username
                        )
                    )
                    personal = PersonalGroup.objects.create(
                        user=user, group=group
                    )
                    logger.info(
                        "Created personal group %r for user %s.",
                        group.name,
                        user.username,
                    )
                # Re-added every time, not just on creation: `save_m2m` may
                # have cleared it since, which is exactly the case this
                # handler exists to repair.
                user.groups.add(personal.group)
        except Exception:
            logger.exception(
                "Failed to create or join a personal group for user %s; they "
                "may not be able to select a group when creating "
                "observations.",
                getattr(user, "username", None),
            )

    transaction.on_commit(_ensure)
