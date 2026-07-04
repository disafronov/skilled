"""Update Q2 Schedule func for the processing task (ID 4).

The proxy.worker indirection was removed in favour of a direct
reference to apps.llm.tasks.worker via settings.Q2_PROCESSING_FUNC.
"""

from django.db import migrations


def update_processing_func(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(id=4).update(func="apps.llm.tasks.worker")


class Migration(migrations.Migration):
    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.RunPython(update_processing_func),
    ]
