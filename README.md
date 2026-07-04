# skilled

Skill-driven AI bot runtime — connects Telegram to any OpenAI-compatible LLM via an asynchronous job queue.

## Architecture

```text
Telegram ──┬── webhook ──> IntakeBuffer ──> Job ──> processing ──> telegram_deliver ──> Telegram
           │                (flush)               │
           └── poll ────────┘                      └─ Worker (profile + wrapper)
           (Q2 schedule)
```

**Two ingestion paths:**

- **Webhook** (primary) — Telegram pushes updates to `/webhook/`. Inbound auth uses `X-Telegram-Bot-Api-Secret-Token` header matched against the bot's `webhook_secret`. Zero polling latency.
- **Polling** (fallback) — scheduled Q2 task `telegram_ingest` periodically fetches updates via `getUpdates`. Webhook auto-registers, self-heals on errors, and falls back to polling with a configurable cooldown.

Both paths accumulate messages into an **IntakeBuffer**, one per bot/chat. Messages are grouped by Telegram `message.date` timestamp — consecutive messages within the debounce window merge into one buffer. A message beyond the window triggers an immediate flush into a `Job`. A scheduled safety flush (`telegram_intake_flush`) catches any leftover open buffer. A Django `post_save` signal schedules downstream tasks via `transaction.on_commit`:

| Signal trigger | Enqueued task |
| -------------- | -------------- |
| Job created | `telegram_ack` — confirm receipt to user |
| Job created | `processing` — call the LLM |
| `llm_finished_at` set | `telegram_deliver` — send response to user |

Scheduled Q2 tasks run the same workers as backup (1-minute interval), giving the system a hybrid push+pull resilience model.

## Core concepts

```text
Skill    — system-level instruction content
Wrapper  — per-bot wrapper instruction
Profile  — model + temperature + other LLM parameters
Provider — API endpoint + auth (OpenAI-compatible)
Bot           — Telegram endpoint / transport identity
Worker        — Execution configuration for a bot. Currently stores LLM profile and wrapper.
IntakeBuffer  — mutable pre-job accumulator (one open buffer per bot/chat)
Job           — finalized execution artifact (immutable after creation)

All tasks flow through `apps/library` (Skill & Wrapper), `apps/inference` (Provider & Profile), `engine/telegram` (Bot, Job, IntakeBuffer + pipeline), `engine/processing` (Worker abstract base), `apps/llm` (Worker model + LLM client), and `apps/ops` (health checks + Q2 cleanup).

## Pipeline

1. **Intake** — `telegram_ingest` or webhook view accumulates message into `IntakeBuffer`, groups by Telegram `message.date`
2. **Flush** — immediate flush on group boundary, or `telegram_intake_flush` (scheduled Q2) as safety backstop
3. **Ack** — `telegram_ack` replies "Added to the processing queue"
4. **LLM** — `processing` calls the configured OpenAI-compatible API
5. **Deliver** — `telegram_deliver` sends the response (text or file) to the user

## Security

- **Field encryption** — `telegram_api_token`, `auth_token`, and `webhook_secret` encrypted at rest with AES-SIV (deterministic, enables DB lookup).
- **Webhook auth** — inbound requests carry `X-Telegram-Bot-Api-Secret-Token` header matched against the bot's `webhook_secret`. Telegram API token is never exposed in URLs or logs.
- **Log masking** — `BotTokenFilter` strips bot tokens from all log output via regex.
- **Production** — `DJANGO_SECRET_KEY` must be strong; `DEBUG` must be `False`.

## Configuration

Key environment variables (see `env.example` for full list):

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `FIELD_ENCRYPTION_KEY` | — | AES-SIV 32-byte hex key (generate via `secrets.token_bytes(32).hex()`) |
| `DJANGO_BASE_URL` | `""` | Public URL for webhook registration; empty = polling only |
| `WEBHOOK_COOLDOWN_SECONDS` | `300` | Seconds to wait before retrying webhook after fallback |
| `WEBHOOK_FALLBACK_PENDING_THRESHOLD` | `5` | Max pending updates before falling back to polling |
| `POLICY_FILE` | `policy.md` | Global system prompt appended to every LLM call |
| `Q2_TELEGRAM_INGEST_MINUTES` | `1` | Polling interval |
| `Q2_PROCESSING_MINUTES` | `1` | LLM processing schedule interval |
| `Q2_TELEGRAM_DELIVER_MINUTES` | `1` | Delivery worker schedule interval |
| `TELEGRAM_ACK_REACTION` | `🤔` | Emoji reaction for queue acknowledgement (empty = disabled) |
| `Q2_LLM_STALE_JOB_SECONDS` | `3600` | Timeout for re-queueing stalled LLM jobs |

## Running

```bash
# Start PostgreSQL
docker compose up -d postgres

# Install dependencies
uv sync

# Apply migrations
uv run python manage.py migrate

# Run all checks (lint, test, dead-code)
make all

# Start dev server + task queue
make run
```

## Health checks

| Endpoint | Purpose |
| -------- | ------- |
| `/health/liveness/` | Process is running |
| `/health/readiness/` | Process can reach critical dependencies |

Implemented in `apps/ops/health.py`. Used by Docker `HEALTHCHECK`.

## Scheduled tasks

| Schedule | Interval | Description |
| -------- | -------- | ----------- |
| `telegram_ingest` (ID 1) | 1 min | Polling fallback |
| `processing` (ID 2) | 1 min | Stale LLM job re-queue |
| `telegram_deliver` (ID 3) | 1 min | Stale delivery re-queue |
| `telegram_intake_flush` (ID 4) | 1 min | Safety flush for open intake buffers |
| `q2_success_cleanup` (ID 5) | 60 min | Cleanup successful Q2 tasks |

Schedules with IDs 1–4 are managed by `engine/telegram/apps.py`, ID 5 by `apps/ops/apps.py`. Admin edits are overwritten on save via `pre_save` signal.

## Management commands

| Command | Description |
| ------- | ----------- |
| `dev` | qcluster + runserver (development) |
| `start` | qcluster + gunicorn (production) |
