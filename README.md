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

```
Telegram ──> telegram_ingest_once (Q2) ──> Job ──> llm_worker_once (Q2) ──> telegram_deliver_once (Q2) ──> Telegram
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
|---------|-------------|
| `telegram_ingest_once` | Poll Telegram for updates, create Jobs |
| `llm_worker_once` | Process one pending Job via LLM |
| `telegram_deliver_once` | Deliver one completed Job to Telegram |
| `dev` | qcluster + runserver (development) |
| `start` | qcluster + gunicorn (production) |
