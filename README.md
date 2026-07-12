# skilled

Skill-driven AI bot runtime that connects Telegram to an OpenAI-compatible LLM
through django-q2.

`skilled` provides the prompt library, inference configuration, concrete LLM
worker, and production runtime. Telegram transport and job orchestration come
from [`django-telegram-q2`](https://github.com/disafronov/django-telegram-q2).

## Architecture

```text
Telegram → django-telegram-q2 → apps.inference → LLM
   ↑                                      │
   └──────────── response delivery ───────┘
```

The application-specific model is built from five concepts:

- **Skill** — reusable system-level instruction content.
- **Wrapper** — per-bot instruction wrapping its selected skill.
- **Provider** — OpenAI-compatible API endpoint and credentials.
- **Profile** — provider, model, temperature, and token settings.
- **Worker** — binds a Telegram bot to a profile and wrapper.

The external package owns `Bot`, `Job`, `IntakeBuffer`, webhook handling, Q2
schedules, processing lifecycle, and Telegram delivery. See its documentation
for pipeline behavior, retries, polling fallback, and package settings.

## Configuration

Copy `env.example` to `.env` and adjust it for the local environment. Important
application settings include:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DJANGO_SECRET_KEY` | development value | Required strong secret in production |
| `FIELD_ENCRYPTION_KEY` | development value | AES-SIV key for encrypted credentials |
| `POLICY_FILE` | `policy.md` | Global system prompt appended to each request |
| `DATABASE_HOST` | `localhost` | PostgreSQL hostname |
| `DATABASE_NAME` | `database` | PostgreSQL database |
| `Q_WORKERS` | `2` | django-q2 worker count |

`env.example` documents the full runtime configuration, including settings
consumed by `django-telegram-q2`.

Providers, profiles, skills, wrappers, bots, and workers are configured through
the Django admin.

## Local development

```bash
# Start local PostgreSQL
docker compose up -d postgres

# Install dependencies and pre-commit hooks
make install

# Apply migrations
make migrate

# Run lint, tests, coverage, and dead-code checks
make all

# Start the development server and Q2 cluster
make run
```

The `django-telegram-q2` dependency is installed directly from Git and pinned
to an exact commit by `uv.lock`. Git must be available during dependency
installation.

## Docker

```bash
make docker-build
make docker-run
```

The production image runs migrations separately, then starts qcluster and
Gunicorn through `manage.py start`. Git is present only in the builder stage.
`compose.yml` supplies local infrastructure and is not a production deployment
definition.

## Health checks

| Endpoint | Purpose |
| -------- | ------- |
| `/health/liveness/` | Process is running |
| `/health/readiness/` | Process can reach the database |

The Docker image uses the readiness endpoint for `HEALTHCHECK`.

## Upgrading from the embedded engine

Earlier versions kept the Telegram pipeline under `engine/`. Migration
`apps.ops.0001_remove_legacy_engine_schedules` removes its obsolete managed Q2
schedules. `django-telegram-q2` creates its current schedules after migrations;
custom schedules are left intact.

## Project structure

```text
apps/
  inference/  — providers, profiles, concrete LLM worker and client
  library/    — skills and wrappers
  ops/        — health checks, process supervision and Q2 maintenance

config/       — Django settings, URLs and WSGI entrypoint
```
