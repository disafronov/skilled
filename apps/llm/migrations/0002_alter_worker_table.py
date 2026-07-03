# Generated manually

from django.db import migrations


class Migration(migrations.Migration):
    """Rename worker_worker → llm_worker after app rename apps.worker → apps.llm."""

    dependencies = [
        ("llm", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="worker",
            table="llm_worker",
        ),
    ]
