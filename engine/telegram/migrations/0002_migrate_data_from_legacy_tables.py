from django.db import migrations


def _table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL", [table])
    return cursor.fetchone()[0]


def _copy_table(cursor, target: str, columns: list[str], source: str):
    """Copy rows from *source* to *target* if *source* exists."""
    if not _table_exists(cursor, source):
        return
    col_sql = ", ".join(columns)
    cursor.execute(rf"INSERT INTO {target} ({col_sql}) SELECT {col_sql} FROM {source}")
    cursor.execute(
        f"SELECT setval(pg_get_serial_sequence('{target}', 'id'),"
        f" COALESCE((SELECT MAX(id) FROM {target}), 0) + 1, false)"
    )


def copy_legacy_data(apps, schema_editor):
    """Copy data from old monolith tables to new split tables."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        _copy_table(
            cursor,
            "telegram_bot",
            [
                "id",
                "name",
                "telegram_api_token",
                "webhook_secret",
                "enabled",
                "telegram_update_offset",
                "webhook_enabled_at",
                "webhook_disabled_at",
                "created_at",
                "updated_at",
            ],
            "bots_bot",
        )
        _copy_table(
            cursor,
            "telegram_job",
            [
                "id",
                "bot_id",
                "reply_target",
                "reply_to_message_id",
                "raw_input",
                "raw_output",
                "error",
                "llm_started_at",
                "llm_finished_at",
                "delivery_started_at",
                "delivery_finished_at",
                "created_at",
                "updated_at",
            ],
            "jobs_job",
        )
        _copy_table(
            cursor,
            "telegram_intakebuffer",
            [
                "id",
                "bot_id",
                "chat_id",
                "reply_to_message_id",
                "text",
                "message_count",
                "last_message_ts",
                "last_received_at",
                "flushed_at",
                "created_at",
                "updated_at",
            ],
            "jobs_intakebuffer",
        )
        _copy_table(
            cursor,
            "llm_worker",
            [
                "id",
                "bot_id",
                "profile_id",
                "wrapper_id",
                "enabled",
                "created_at",
                "updated_at",
            ],
            "jobs_worker",
        )

        for old_table in ["bots_bot", "jobs_job", "jobs_intakebuffer", "jobs_worker"]:
            cursor.execute(f"DROP TABLE IF EXISTS {old_table} CASCADE")


class Migration(migrations.Migration):

    dependencies = [
        ("telegram", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            copy_legacy_data,
            elidable=True,
        ),
    ]
