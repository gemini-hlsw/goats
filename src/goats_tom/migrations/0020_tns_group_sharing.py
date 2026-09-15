"""Add the TNS group sharing tables, and backfill from existing credentials.

The backfill matters more than it looks. `TNSLogin.group_names` already
holds every group each user's bot posts to, and the new tables hang settings
off those names -- so without this step, every user who already had
credentials would open the credential page after upgrading and find no
groups to configure, with no indication that saving the form again would
make them appear.

The backfill creates rows with `allow_join_requests` left at its default of
`False`. Nothing is shared as a side effect of upgrading; sharing a bot means
posts go out under somebody's name, so it stays a decision each owner makes.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_groups_from_logins(apps, schema_editor):
    """Create a `TNSGroup` for every name already on a `TNSLogin`.

    Notes
    -----
    Uses the historical models via `apps.get_model`, not the real ones, so
    this keeps working if `goats_tom.tns_membership.sync_groups_for_login`
    later changes shape. Calling that helper here instead would couple a
    frozen migration to live code.

    `TNSLogin.token` is a `goats_tom.encryption.EncryptedField`, but nothing
    here touches it -- only `group_names`, which is plain JSON. That keeps
    the migration runnable even if the key is unavailable.
    """
    TNSLogin = apps.get_model("goats_tom", "TNSLogin")
    TNSGroup = apps.get_model("goats_tom", "TNSGroup")

    for login in TNSLogin.objects.all().iterator():
        names = login.group_names or []
        seen = set()
        for raw in names:
            name = str(raw).strip()
            # Duplicates within one user's list would violate the unique
            # constraint. A hand-edited list can easily contain them, and a
            # migration that crashes on upgrade is a far worse outcome than
            # silently collapsing two identical names into one row.
            if not name or name in seen:
                continue
            seen.add(name)
            TNSGroup.objects.get_or_create(
                owner_id=login.user_id, name=name
            )


def remove_groups(apps, schema_editor):
    """Reverse the backfill.

    Notes
    -----
    Deletes every `TNSGroup`, which is correct only because the table did
    not exist before this migration -- there is nothing here that predates
    it. The table is dropped immediately afterwards by the reverse of
    `CreateModel` anyway; this exists so the migration is reversible
    without Django refusing at the `RunPython` step.
    """
    apps.get_model("goats_tom", "TNSGroup").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("goats_tom", "0019_dragonsrun_output_written_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TNSGroup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("allow_join_requests", models.BooleanField(default=False)),
                (
                    "recommended_authors",
                    models.TextField(blank=True, default=""),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tns_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "TNS group",
                "verbose_name_plural": "TNS groups",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TNSGroupJoinRequest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("denied", "Denied"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tns_join_requests_decided",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tns_join_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tns_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="join_requests",
                        to="goats_tom.tnsgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "TNS group join request",
                "verbose_name_plural": "TNS group join requests",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TNSGroupMembership",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tns_memberships_granted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tns_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="goats_tom.tnsgroup",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tns_group_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "TNS group membership",
                "verbose_name_plural": "TNS group memberships",
                "ordering": ["user__username"],
            },
        ),
        migrations.CreateModel(
            name="TNSSubmissionRecord",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "username",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "group_name",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "bot_id",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                (
                    "object_name",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("report", "Discovery report"),
                            ("classify", "Classification"),
                        ],
                        max_length=16,
                    ),
                ),
                ("succeeded", models.BooleanField(default=False)),
                (
                    "iau_name",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "target_pk",
                    models.PositiveIntegerField(
                        blank=True, db_index=True, null=True
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tns_submissions_via_my_bot",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tns_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tns_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submissions",
                        to="goats_tom.tnsgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "TNS submission record",
                "verbose_name_plural": "TNS submission records",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="tnsgroup",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"), name="unique_tns_group_per_owner"
            ),
        ),
        migrations.AddConstraint(
            model_name="tnsgroupjoinrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "pending")),
                fields=("requester", "tns_group"),
                name="unique_pending_tns_join_request",
            ),
        ),
        migrations.AddConstraint(
            model_name="tnsgroupmembership",
            constraint=models.UniqueConstraint(
                fields=("tns_group", "user"),
                name="unique_tns_membership_per_group_and_user",
            ),
        ),
        migrations.RunPython(create_groups_from_logins, remove_groups),
    ]
