"""Scope trigger records to an ingestion run and persist the picker's target.

Written by hand rather than generated: `makemigrations` cannot tell whether
`GeminiTriggerRecord.generation` became `run_number` by rename or by
replacement, and stops to ask. It is a replacement. The two fields mean
different things -- `generation` advances on stop as well as start, so records
keyed on it were discarded merely by stopping ingestion -- and the old values
are meaningless under the new key. Dropping the column discards them, which is
correct: a stale run's outcomes should not be attributed to the current run.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("goats_tom", "0009_trigger_records_per_run"),
    ]

    operations = [
        # The constraint references the column, so it goes first.
        migrations.RemoveConstraint(
            model_name="geminitriggerrecord",
            name="unique_gemini_trigger_per_locus_per_run",
        ),
        migrations.RemoveField(
            model_name="geminitriggerrecord",
            name="generation",
        ),
        migrations.AddField(
            model_name="geminitriggerrecord",
            name="run_number",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.AddConstraint(
            model_name="geminitriggerrecord",
            constraint=models.UniqueConstraint(
                fields=("subscription", "run_number", "locus_id"),
                name="unique_gemini_trigger_per_locus_per_run",
            ),
        ),
        migrations.AddField(
            model_name="antaresstreamsubscription",
            name="run_number",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="antaresstreamsubscription",
            name="gpp_target_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="antaresstreamsubscription",
            name="gpp_target_overrides",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="antaresstreamsubscription",
            name="gpp_instrument",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
