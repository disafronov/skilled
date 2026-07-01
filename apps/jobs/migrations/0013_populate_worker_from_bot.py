"""Data migration: populate Worker from Bot profile/wrapper fields."""

from django.db import migrations


def populate_worker_from_bot(apps, _) -> None:
    Bot = apps.get_model("bots", "Bot")
    Worker = apps.get_model("jobs", "Worker")
    for bot in Bot.objects.iterator():
        Worker.objects.create(
            bot=bot,
            profile=bot.profile,
            wrapper=bot.wrapper,
            enabled=bot.enabled,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0012_alter_intakebuffer_last_message_ts_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_worker_from_bot, migrations.RunPython.noop),
    ]
