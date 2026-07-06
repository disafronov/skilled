"""Split Job processing and delivery error storage."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("telegram", "0005_job_processing_finished_requires_started"),
    ]

    operations = [
        migrations.RenameField(
            model_name="job",
            old_name="error",
            new_name="processing_error",
        ),
        migrations.AddField(
            model_name="job",
            name="delivery_error",
            field=models.TextField(blank=True, null=True),
        ),
    ]
