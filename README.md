# skilled

Skill-driven AI bot runtime.

## Core concepts

- Skill — semantic behavior
- Wrapper — execution contract
- Bot — transport endpoint
- Job — execution artifact

## Architecture

Telegram -> Job Queue -> LLM Worker -> Response

## API Compatibility

Uses OpenAI-compatible Chat Completions API (`/chat/completions`).
Works with any OpenAI-compatible provider.

## Pipeline

```text
Telegram ──> telegram_ingest (Q2) ──> Job ──> llm_worker (Q2) ──> telegram_deliver (Q2) ──> Telegram
```

## Running

```bash
# Start database
docker compose up -d postgres

# Apply migrations
uv run python manage.py migrate

# Run all checks
make all

# Start dev server + task queue
make run
```

## Management Commands

| Command | Description |
| ------- | ----------- |
| `dev` | qcluster + runserver (development) |
| `start` | qcluster + gunicorn (production) |

## Health Checks

| Endpoint | Purpose |
| ---------- | ----------- |
| `/health/liveness/` | Process is running |
| `/health/readiness/` | Process can reach critical dependencies |

The Docker image uses `/health/readiness/` for its `HEALTHCHECK`.
