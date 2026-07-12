# skilled

Skill-driven AI bot runtime that connects Telegram to an OpenAI-compatible LLM through django-q2.

Telegram transport and job orchestration are provided by the external
[`django-telegram-q2`](https://github.com/disafronov/django-telegram-q2)
package. This repository supplies the LLM implementation, prompt library, and
production runtime around it.

## Architecture

```text
Telegram ──┬── webhook ──> IntakeBuffer ──> Job ──> processing ──> telegram_deliver ──> Telegram
           │                (flush)               │
           └── poll ────────┘                      └─ Worker (profile + wrapper)
           (Q2 schedule)
```

**Two ingestion paths:**

- **Webhook** (primary) — Telegram pushes updates to `/webhook/`. Inbound auth uses `X-Telegram-Bot-Api-Secret-Token` header matched against the bot's `webhook_secret`. Zero polling latency.
- **Setup** — Q2 schedule `django_telegram_q2.telegram.setup` runs `telegram_setup` to manage webhook registration, health checks, cleanup, and fallback state.
- **Polling** (fallback) — Q2 schedule `django_telegram_q2.telegram.ingest` runs `telegram_ingest` to periodically fetch updates via `getUpdates` when webhook is not active.

Both paths accumulate messages into an **IntakeBuffer**, one per bot/chat. Messages are grouped by Telegram `message.date` timestamp — consecutive messages within the debounce window merge into one buffer. A message beyond the window triggers an immediate flush into a `Job`. A scheduled safety flush (`django_telegram_q2.telegram.intake_flush`) catches any leftover open buffer. A Django `post_save` signal schedules downstream tasks via `transaction.on_commit`:

| Signal trigger | Enqueued task |
| -------------- | -------------- |
| Job created | `telegram_ack` — confirm receipt to user |
| Job created | `processing` — call the LLM |
| `processing_finished_at` set | `telegram_deliver` — send response to user |

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
```

All tasks flow through `apps/library` (Skill & Wrapper), `apps/inference` (Provider, Profile & Worker), the external `django-telegram-q2` package (Bot, Job, IntakeBuffer + pipeline), and `apps/ops` (health checks + Q2 cleanup).

## Pipeline

1. **Intake** — `telegram_ingest` or webhook view accumulates message into `IntakeBuffer`, groups by Telegram `message.date`
2. **Flush** — immediate flush on group boundary, or `telegram_intake_flush` (scheduled Q2) as safety backstop
3. **Ack** — `telegram_ack` sets a reaction emoji on the user's message
4. **Processing** — `processing` calls the configured OpenAI-compatible API
5. **Deliver** — `telegram_deliver` sends successful responses as files and errors as text messages

Processing jobs can be re-queued when stale because no user-visible side effect has happened yet. Delivery is different: once `delivery_started_at` is set, Telegram may already have accepted the message even if the worker later sees an error. The scheduled `telegram_deliver` task therefore only drains jobs that have not started delivery yet; it does not automatically resend an ambiguous successful payload and risk duplicate replies.

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
| `Q2_TELEGRAM_SETUP_MINUTES` | `1` | Webhook setup / fallback management interval |
| `Q2_TELEGRAM_INGEST_MINUTES` | `1` | Polling interval when webhook is not active |
| `Q2_PROCESSING_MINUTES` | `1` | LLM processing schedule interval |
| `Q2_TELEGRAM_DELIVER_MINUTES` | `1` | Delivery worker schedule interval |
| `Q2_TELEGRAM_INTAKE_FLUSH_MINUTES` | `1` | Stale intake-buffer flush interval |
| `Q2_SUCCESS_CLEANUP_MINUTES` | `60` | Successful Q2 task cleanup interval |
| `TELEGRAM_ACK_REACTION` | `🤔` | Emoji reaction for queue acknowledgement (empty = disabled) |
| `Q2_PROCESSING_STALE_JOB_SECONDS` | `3600` | Timeout for re-queueing stalled processing jobs |

## Local development

```bash
# Start PostgreSQL
docker compose up -d postgres

# Install dependencies and pre-commit hooks
make install

# Apply migrations
make migrate

# Run all checks (lint, test, dead-code)
make all

# Start dev server + task queue
make run
```

The `django-telegram-q2` dependency is installed directly from Git. The exact
commit is pinned in `uv.lock`; Git must therefore be available when dependencies
are installed. The Docker builder stage includes Git, while the runtime image
does not.

## Docker

```bash
# Build the production image
make docker-build

# Run migrations, ensure the configured superuser exists, and start the image
make docker-run
```

`compose.yml` only supplies local infrastructure such as PostgreSQL. It is not a
production deployment definition.

## Upgrading from the embedded engine

Earlier versions kept the Telegram pipeline under `engine/`. Migration
`apps.ops.0001_remove_legacy_engine_schedules` deletes its obsolete managed Q2
schedules during `make migrate`. The external package then creates the current
`django_telegram_q2.*` schedules through Django's `post_migrate` signal. Custom
Q2 schedules are not removed.

## Health checks

| Endpoint | Purpose |
| -------- | ------- |
| `/health/liveness/` | Process is running |
| `/health/readiness/` | Process can reach critical dependencies |

Implemented in `apps/ops/health.py`. Used by Docker `HEALTHCHECK`.

## Scheduled tasks

| Schedule | Interval | Description |
| -------- | -------- | ----------- |
| `django_telegram_q2.telegram.setup` | 1 min | Webhook setup, health check, and fallback management |
| `django_telegram_q2.telegram.ingest` | 1 min | Polling fallback |
| `django_telegram_q2.telegram.deliver` | 1 min | Drain completed jobs that have not started delivery |
| `django_telegram_q2.telegram.intake_flush` | 1 min | Safety flush for open intake buffers |
| `django_telegram_q2.processing` | 1 min | Stale processing job re-queue |
| `q2_success_cleanup` | 60 min | Cleanup successful Q2 tasks |

Telegram pipeline schedules are managed by `django-telegram-q2`; the Q2 cleanup schedule is managed by `apps/ops/apps.py`. Managed schedules are identified by stable names, not fixed primary keys. Admin edits are overwritten on save via `pre_save` signal.

## Project structure

```text
django-telegram-q2 (external Git dependency)
  telegram/        — transport, models, pipeline, schedules, and Worker base
  common/          — encryption, admin, logging, and schedule utilities

apps/              — skilled-specific consumer code
  inference/       — concrete LLM implementation (Provider, Profile, Worker)
  library/         — Skill & Wrapper models (prompt content)
  ops/             — health checks, Q2 cleanup, and upgrade migrations

config/            — Django settings, URLs, WSGI
```

The reusable Django Telegram job pipeline is provided by `django-telegram-q2`.
`skilled` is a working reference implementation that consumes it.

## Management commands

| Command | Description |
| ------- | ----------- |
| `dev` | qcluster + runserver (development) |
| `start` | qcluster + gunicorn (production) |

Prefer the corresponding Makefile targets (`make run`, `make q2`, `make
migrate`, and `make docker-build`) for development and verification because
they provide the expected tooling environment.
