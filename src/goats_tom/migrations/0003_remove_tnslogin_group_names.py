"""Make `TNSGroup` rows the only record of which groups a bot may file under.

The names lived in a JSON list on `TNSLogin`, which made the text itself the
identity of a group: correcting a typo in it silently revoked everyone
approved for the old spelling. Rows carry that identity instead, so a rename
is an edit the memberships follow.
"""

from django.db import migrations


def create_groups_from_names(apps, schema_editor):
    """Give every name still listed on a login a row of its own.

    Most already have one -- they were created on read -- so this only picks
    up logins that were never opened since group sharing was added.
    """
    TNSLogin = apps.get_model("goats_tom", "TNSLogin")
    TNSGroup = apps.get_model("goats_tom", "TNSGroup")

    for login in TNSLogin.objects.all():
        seen = set()
        for name in login.group_names or []:
            name = name.strip()
            # Names differing only by whitespace collapse once stripped,
            # which would make a stray space a unique-constraint violation.
            if not name or name in seen:
                continue
            seen.add(name)
            TNSGroup.objects.get_or_create(owner_id=login.user_id, name=name)


def restore_names_from_groups(apps, schema_editor):
    """Write the names back onto the logins, for a reverse migration.

    Settings and memberships on those rows cannot be represented in a list of
    strings and are left behind rather than lost: the rows themselves stay.
    """
    TNSLogin = apps.get_model("goats_tom", "TNSLogin")
    TNSGroup = apps.get_model("goats_tom", "TNSGroup")

    for login in TNSLogin.objects.all():
        login.group_names = list(
            TNSGroup.objects.filter(owner_id=login.user_id)
            .order_by("name")
            .values_list("name", flat=True)
        )
        login.save(update_fields=["group_names"])


class Migration(migrations.Migration):
    dependencies = [
        ("goats_tom", "0002_tns_group_sharing"),
    ]

    operations = [
        # Before the column goes: afterwards the names are unreadable.
        migrations.RunPython(create_groups_from_names, restore_names_from_groups),
        migrations.RemoveField(
            model_name="tnslogin",
            name="group_names",
        ),
    ]
