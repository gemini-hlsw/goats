"""Find -- and optionally repair -- objects nobody can see.

With ``TARGET_PERMISSIONS_ONLY = False`` every observation record and data
product carries its own permissions. Anything created without them is present
in the database, present on disk, and visible to **nobody** -- including the
person who created it. Nothing errors; the object simply never appears.

That failure has now occurred four separate times, each in a different
creation path: Gemini triggering, "add an existing observation", GOA
downloads, and manual uploads. Each was fixed where it happened, but the
pattern is the point -- any future code that creates one of these objects
without assigning permissions fails the same silent way.

This command does not prevent that. It makes it *visible*, which is the next
best thing: run it after adding any code that creates observations or data
products, and it will say plainly whether they are reachable.

Repairing them::

    # report only
    python manage.py check_object_permissions

    # grant each to its recorded creator, where one exists
    python manage.py check_object_permissions --fix

    # one file, to a named owner, when a batch is not all one person's
    python manage.py check_object_permissions \\
        --fix --only ANT2020bk53s_lightcurve --assign-to jsmith
"""

__all__ = ["Command"]

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from guardian.shortcuts import assign_perm, get_users_with_perms
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord



def _infer_owner(obj):
    """Return the recorded creator of an orphaned object, or `None`.

    Parameters
    ----------
    obj : `ObservationRecord` or `DataProduct`
        The object with no permissions.

    Returns
    -------
    tuple
        ``(user, reason)``. `user` is `None` when no creator is recorded, and
        `reason` says so -- which is what gets printed, so the operator
        decides rather than the command guessing.

    Notes
    -----
    Only one signal is used: `ObservationRecord.user`, which TOM sets to
    whoever created the record. A data product inherits it through its
    observation record.

    An earlier version fell back to whoever held `change_target` on the
    object's target when exactly one user qualified. That is wrong, and
    wrong in a way that looks safe: owning a target says nothing about who
    triggered a particular observation on it, and on a shared target those
    are routinely different people. A single candidate makes the guess
    convenient, not correct.

    So there is no fallback. An object with no recorded creator is reported
    and left alone, and `--assign-to` exists for an operator who knows
    something the database does not.
    """
    record = obj if hasattr(obj, "facility") else getattr(
        obj, "observation_record", None
    )
    if record is None:
        return None, "no observation record to attribute it to"
    creator = getattr(record, "user", None)
    if creator is None:
        return None, "no creator recorded"
    return creator, "recorded creator"


CHECKS = (
    (ObservationRecord, "tom_observations", "observationrecord", "observation_id"),
    (DataProduct, "tom_dataproducts", "dataproduct", "product_id"),
)


class Command(BaseCommand):
    """Report objects with no per-object permissions, and optionally fix them."""

    help = (
        "Find observation records and data products that no user can see "
        "because they were created without per-object permissions."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--fix",
            action="store_true",
            help=(
                "Grant permissions to each object's inferred owner. Objects "
                "whose owner cannot be established are reported and left "
                "alone."
            ),
        )
        parser.add_argument(
            "--assign-to",
            metavar="USERNAME",
            help=(
                "Only for objects whose owner cannot be inferred, and only "
                "with --fix. Use after reading the report, once you are sure "
                "they are all this person's."
            ),
        )
        parser.add_argument(
            "--only",
            metavar="IDENTIFIER",
            help=(
                "Restrict to the single object with this product_id or "
                "observation_id. Use with --fix --assign-to to repair one "
                "file at a time when a batch of orphans does not all belong "
                "to the same person."
            ),
        )

    def handle(self, *args, **options) -> None:
        """Scan both models, reporting or repairing what nobody can see."""
        from django.conf import settings

        if settings.TARGET_PERMISSIONS_ONLY:
            self.stdout.write(
                "TARGET_PERMISSIONS_ONLY is on: the target governs access to "
                "everything beneath it, so per-object permissions are unused "
                "and nothing here can be orphaned."
            )
            return

        fallback = None
        if options["assign_to"]:
            if not options["fix"]:
                raise CommandError("--assign-to does nothing without --fix.")
            fallback = (
                get_user_model().objects.filter(username=options["assign_to"]).first()
            )
            if fallback is None:
                raise CommandError(f"No user named {options['assign_to']!r}.")

        only = options["only"]
        matched = False

        orphaned_total = repaired = unresolved = 0
        for model, app_label, model_name, label_field in CHECKS:
            candidates = model.objects.all()
            if only:
                # Scoped by the identifier the report prints, so an operator
                # can paste a line straight back in. An identifier that
                # matches neither model is an error rather than a silent
                # no-op, since "nothing orphaned" would read as success.
                candidates = candidates.filter(**{label_field: only})
                if candidates.exists():
                    matched = True
                elif model.objects.filter(**{label_field: only}).exists():
                    matched = True

            # Checked per object rather than with one query: guardian stores
            # user and group permissions in separate tables, and an object is
            # only orphaned when *both* are empty.
            orphaned = [
                obj
                for obj in candidates
                if not get_users_with_perms(obj, with_group_users=True).exists()
            ]
            orphaned_total += len(orphaned)
            if only:
                self.stdout.write(
                    f"{model.__name__}: {len(orphaned)} of {candidates.count()} "
                    f"matching {only!r} visible to nobody."
                )
            else:
                self.stdout.write(
                    f"{model.__name__}: {len(orphaned)} of {model.objects.count()} "
                    "visible to nobody."
                )

            for obj in orphaned:
                label = getattr(obj, label_field, None) or obj.pk
                owner, reason = _infer_owner(obj)
                if owner is None and fallback is not None:
                    owner, reason = fallback, "assigned by --assign-to"

                if owner is None:
                    unresolved += 1
                    self.stdout.write(
                        self.style.WARNING(f"    {label} -- owner unknown: {reason}")
                    )
                    continue
                if not options["fix"]:
                    self.stdout.write(f"    {label} -> {owner.username} ({reason})")
                    continue
                for action in ("view", "change", "delete"):
                    assign_perm(f"{app_label}.{action}_{model_name}", owner, obj)
                repaired += 1
                self.stdout.write(
                    f"    {label} -> granted to {owner.username} ({reason})"
                )

        if only and not matched:
            raise CommandError(
                f"No observation record or data product with the identifier "
                f"{only!r}."
            )
        if orphaned_total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing orphaned."))
            return
        if not options["fix"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{orphaned_total} object(s) unreachable. Re-run with --fix "
                    "to grant each to the owner shown above."
                )
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} object(s)."))
        if unresolved:
            self.stdout.write(
                self.style.WARNING(
                    f"{unresolved} left alone: no owner could be established. "
                    "Check the reasons above, then use --assign-to USERNAME "
                    "if they really do all belong to one person."
                )
            )
