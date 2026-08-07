"""Signal handlers for the ANTARES stream feature.

Registered from `goats_tom.apps.GOATSTomConfig.ready`.
"""

__all__ = [
    "block_shared_target_deletion",
    "clear_target_save_records",
    "create_pi_group_for_kafka_credentials",
    "ensure_user_has_a_group",
]

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
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


@receiver(post_delete, dispatch_uid="clear_antares_target_saves")
def clear_target_save_records(sender, instance, **kwargs) -> None:
    """Drop `AntaresTargetSave` rows for a target that has been deleted.

    Parameters
    ----------
    sender : type
        The sending model class. Ignored unless it is the configured target
        model.
    instance : `tom_targets.models.Target`
        The target being deleted.
    **kwargs
        Remaining signal arguments.

    Notes
    -----
    A save record answers "who saved this target". Once the target is gone it
    describes nothing, and leaving it behind makes the system act as though
    the target still exists -- auto-save skipped such loci permanently,
    because the record was taken as proof a target was there.

    Connected without a `sender` and filtered here instead, because the target
    model is swappable and importing it at module import time would run before
    the app registry is ready.

    Matched on `locus_id` against the target's name and aliases, mirroring how
    `goats_tom.antares_target_save.locus_is_saved_as_target` decides a locus is
    saved -- a target may be recorded under either.

    Failures are logged, never raised: a leftover record is untidy, but making
    a deletion fail because of it would be worse.
    """
    # Imported rather than looked up by label: the concrete class is
    # `BaseTarget` on the pinned TOM Toolkit, and the model is swappable, so
    # `apps.get_model("tom_targets", "Target")` raises LookupError -- which
    # made an earlier version of this handler return silently and do nothing.
    # `tom_targets.models.Target` always resolves to whatever is configured.
    from tom_targets.models import Target  # noqa: PLC0415

    if not isinstance(instance, Target):
        return

    try:
        from goats_tom.models import AntaresTargetSave  # noqa: PLC0415

        names = {instance.name}
        # `aliases` may already be gone if the delete cascaded first, so this
        # is best-effort rather than assumed available.
        try:
            names.update(instance.aliases.values_list("name", flat=True))
        except Exception:  # noqa: BLE001
            pass

        locus_names = [n for n in names if n]

        deleted, _ = AntaresTargetSave.objects.filter(
            locus_id__in=locus_names
        ).delete()
        if deleted:
            logger.info(
                "Removed %d ANTARES save record(s) for deleted target %r.",
                deleted,
                instance.name,
            )

        # Trigger records go too. They key on `locus_id` with no link to the
        # target, so they used to outlive it -- and because a record blocks
        # any further trigger for that locus in the same run, a deleted target
        # left the locus permanently untriggerable with nothing on screen to
        # explain why. Deleting a target now really is a clean slate.
        from goats_tom.models import GeminiTriggerRecord  # noqa: PLC0415

        triggers_deleted, _ = GeminiTriggerRecord.objects.filter(
            locus_id__in=locus_names
        ).delete()
        if triggers_deleted:
            logger.info(
                "Removed %d Gemini trigger record(s) for deleted target %r.",
                triggers_deleted,
                instance.name,
            )
    except Exception:
        logger.exception(
            "Failed to clear ANTARES save records for deleted target %r; "
            "auto-save may skip that locus until they are removed.",
            getattr(instance, "name", None),
        )


@receiver(pre_delete, dispatch_uid="block_shared_antares_target_deletion")
def block_shared_target_deletion(sender, instance, **kwargs) -> None:
    """Refuse to delete a target that more than one team holds.

    Parameters
    ----------
    sender : type
        The sending model class. Ignored unless it is the target model.
    instance : `tom_targets.models.Target`
        The target about to be deleted.
    **kwargs
        Remaining signal arguments.

    Raises
    ------
    `goats_tom.antares_target_save.SharedTargetDeletionError`
        If two or more PIs have save records for this target.

    Notes
    -----
    There is one `Target` per locus and teams share it rather than each
    getting a copy (see `goats_tom.antares_target_save.save_locus_as_target`).
    So deleting one removes it from every team at once -- silently, since a PI
    looking at their own dashboard cannot see who else holds it. Refusing is
    the only option that cannot surprise somebody.

    Enforced here rather than only in the delete view so it also covers the
    Django admin, the shell and any bulk delete. `pre_delete` runs inside the
    deletion's transaction, so raising rolls the whole thing back.

    `goats_tom.views.target_delete.TargetDeleteView` checks the same condition
    up front and reports it properly. That check is not redundant: the view
    tears down observation records before deleting the target, so relying on
    this signal alone would destroy them and only then refuse.

    Django sends `pre_delete` inside the collector's own transaction, opened
    with ``savepoint=False``, so raising marks the enclosing transaction for
    rollback. A caller already inside `transaction.atomic` that wants to carry
    on afterwards must wrap the delete in its own atomic block; otherwise the
    first query after the refusal fails with `TransactionManagementError`.
    Callers that simply let the refusal propagate need do nothing.
    """
    from tom_targets.models import Target  # noqa: PLC0415

    if not isinstance(instance, Target):
        return

    from goats_tom.antares_target_save import (  # noqa: PLC0415
        SharedTargetDeletionError,
        target_saver_usernames,
    )

    savers = target_saver_usernames(instance)
    if len(savers) > 1:
        raise SharedTargetDeletionError(
            f"Target {instance.name!r} is shared by {len(savers)} teams "
            f"({', '.join(savers)}) and cannot be deleted. Deleting it would "
            f"remove it from all of them."
        )
