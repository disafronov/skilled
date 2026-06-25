# Generated manually: add enabled field to Bot model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bots", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bot",
            name="enabled",
            field=models.BooleanField(
                default=True,
                help_text="Is this bot active for message processing?",
            ),
        ),
    ]
