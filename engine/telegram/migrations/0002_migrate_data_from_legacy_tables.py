from django.db import migrations


def _table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL", [table])
    return cursor.fetchone()[0]


def copy_legacy_data(apps, schema_editor):
    """Copy data from old bots/jobs tables to new telegram/worker tables."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if not _table_exists(cursor, "bots_bot"):
            return

        cursor.execute(r"""
            INSERT INTO telegram_bot (
                id, name, telegram_api_token, webhook_secret,
                enabled, telegram_update_offset,
                webhook_enabled_at, webhook_disabled_at,
                created_at, updated_at
            )
            SELECT
                id, name, telegram_api_token, webhook_secret,
                enabled, telegram_update_offset,
                webhook_enabled_at, webhook_disabled_at,
                created_at, updated_at
            FROM bots_bot
            """)
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('telegram_bot', 'id'),"
            " COALESCE((SELECT MAX(id) FROM telegram_bot), 0) + 1, false)"
        )

        cursor.execute(r"""
            INSERT INTO telegram_job (
                id, bot_id, reply_target, reply_to_message_id,
                raw_input, raw_output, error,
                llm_started_at, llm_finished_at,
                delivery_started_at, delivery_finished_at,
                created_at, updated_at
            )
            SELECT
                id, bot_id, reply_target, reply_to_message_id,
                raw_input, raw_output, error,
                llm_started_at, llm_finished_at,
                delivery_started_at, delivery_finished_at,
                created_at, updated_at
            FROM jobs_job
            """)
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('telegram_job', 'id'),"
            " COALESCE((SELECT MAX(id) FROM telegram_job), 0) + 1, false)"
        )

        cursor.execute(r"""
            INSERT INTO telegram_intakebuffer (
                id, bot_id, chat_id, reply_to_message_id,
                text, message_count,
                last_message_ts, last_received_at,
                flushed_at,
                created_at, updated_at
            )
            SELECT
                id, bot_id, chat_id, reply_to_message_id,
                text, message_count,
                last_message_ts, last_received_at,
                flushed_at,
                created_at, updated_at
            FROM jobs_intakebuffer
            """)
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('telegram_intakebuffer', 'id'),"
            " COALESCE((SELECT MAX(id) FROM telegram_intakebuffer), 0) + 1, false)"
        )

        cursor.execute(r"""
            INSERT INTO llm_worker (
                id, bot_id, profile_id, wrapper_id,
                enabled, created_at, updated_at
            )
            SELECT
                id, bot_id, profile_id, wrapper_id,
                enabled, created_at, updated_at
            FROM jobs_worker
            """)
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('llm_worker', 'id'),"
            " COALESCE((SELECT MAX(id) FROM llm_worker), 0) + 1, false)"
        )

        cursor.execute("DROP TABLE IF EXISTS bots_bot CASCADE")
        cursor.execute("DROP TABLE IF EXISTS jobs_job CASCADE")
        cursor.execute("DROP TABLE IF EXISTS jobs_intakebuffer CASCADE")
        cursor.execute("DROP TABLE IF EXISTS jobs_worker CASCADE")


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
