"""Store the submitter's full name on the TNS submission log.

The log has to keep making sense after an account is deleted, so it snapshots
what it needs rather than following a foreign key. It snapshotted the
username, which is half of a login credential and identifies nobody to a
colleague, so the column can no longer be shown. This adds the name that can.

Backfills from the current user where the account still exists. Rows whose
submitter is already gone keep a blank name and render as a dash -- the
original name was never recorded, and inventing one from the username would
be worse than admitting it is unknown.
"""

from django.db import migrations, models


def backfill_display_names(apps, schema_editor):
    """Fill `display_name` from each submitter's current full name.

    Notes
    -----
    Reads the live name rather than any historical one, since no historical
    one was ever stored. A user who has since changed their name will show
    the new one on old rows; that is the only information available, and it
    still points at the right person.

    Uses `first_name`/`last_name` directly instead of `get_full_name`,
    because `apps.get_model` returns a historical model without the real
    `User` class's methods.
    """
    TNSSubmissionRecord = apps.get_model("goats_tom", "TNSSubmissionRecord")

    for record in TNSSubmissionRecord.objects.select_related(
        "submitted_by"
    ).iterator():
        user = record.submitted_by
        if user is None:
            continue
        name = f"{user.first_name} {user.last_name}".strip()
        if name:
            record.display_name = name
            record.save(update_fields=["display_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("goats_tom", "0020_tns_group_sharing"),
    ]

    operations = [
        migrations.AddField(
            model_name="tnssubmissionrecord",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.RunPython(
            backfill_display_names, migrations.RunPython.noop
        ),
    ]
