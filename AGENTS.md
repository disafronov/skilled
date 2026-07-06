# AGENTS.md

## Documentation Convention

- **Docstrings**: required on all model classes, QuerySet methods, public functions, and modules.
- **HOW comments**: required when the code takes a non-obvious approach:
  - `EncryptedCharField.get_prep_value` in `engine/common/fields.py` — AES-SIV ciphertext bypasses ORM value preparation (skips `CharField.get_prep_value` to avoid double-encryption).
  - `transaction.on_commit` in `engine/telegram/signals.py` — avoids orphan Q2 tasks on rollback.
  - Disabled bot webhook cleanup in `telegram_ingest` — not in Bot.save to avoid API calls in admin flow.
  - `skip_locked=True` in `telegram_ingest` — avoids queueing behind other workers.
  - Double `select_for_update` in `telegram_ingest` — re-reads offset after get_updates.
  - Delivery retry semantics in `engine/telegram/tasks.py` — processing can be re-queued when stale, but delivery does not automatically resend an ambiguous payload after `delivery_started_at` because Telegram sends are not idempotent.

## Commands

```sh
make install          # deps + pre-commit hooks
make format           # black + isort
make lint             # black --check, isort --check-only, flake8, mypy, bandit
make test             # pytest with coverage (100% fail_under)
make dead-code        # vulture
make all              # lint → test → dead-code
make run              # migrate + createsuperuser + dev server (qcluster + runserver)
make q2               # qcluster only
make makemigrations   # DJANGO_SECRET_KEY already set
make migrate          # DJANGO_SECRET_KEY already set
```

**Never** run `manage.py test` — it's intentionally blocked. Use `make test` or `uv run pytest`.

Run a single test: `uv run pytest path/to/test_file.py::test_name -v`
DJANGO_SECRET_KEY is required for any Django command; `make` wrappers set it automatically.

## Lint & Type Check

- **black** (line-length=88), **isort** (profile=black), **flake8** (max-line-length=88, ignores E203/W503)
- **mypy**: strict mode (disallow_untyped_defs, disallow_incomplete_defs, disallow_untyped_decorators, strict_equality). Uses django-stubs plugin. Excludes: tests/, migrations/, manage.py. django-q2 stubs ignored via ignore_missing_imports.
- **bandit**: security lint
- **vulture**: dead code detection

Order: `lint` → `test` → `dead-code`

## Test Quirks

- Settings module: `config.settings_pytest` (disables WhiteNoise + SSL redirects)
- Coverage: 100% branch coverage required (`fail_under=100`, `branch=true`, `parallel=true`)
- Parallel: `-n auto` (pytest-xdist)

## Architecture

Telegram → Job Queue (django-q2) → LLM Worker → Telegram delivery

- `apps/ops/q2.py` — django-q2 scheduled task functions (cleanup_q2_successes)
- `apps/ops/health.py` — `/health/liveness/`, `/health/readiness/` (Docker HEALTHCHECK)
- `apps/ops/apps.py` — Q2 schedule management for cleanup task
- `engine/telegram` — Bot, Job, IntakeBuffer models; pipeline tasks (telegram_ingest, processing, telegram_deliver, telegram_flush_intake_buffers); webhook view; admin; signals; Q2 schedule management via `apps.py`
- `engine/processing` — Abstract Worker base class (processing pipeline foundation)
- `engine/telegram/client.py` — Telegram Bot API client
- `apps/library` — Skill & Wrapper models (prompt content)
- `apps/inference` — Provider, Profile & Worker models; LLM client; task orchestrator
- `config/` — Django settings, urls, wsgi

## Gotchas

- **DJANGO_SECRET_KEY**: Must be set for any `manage.py` command. Makefile uses `unsafe-secret-key-for-tooling`.
- **Q2 schedules** are managed by stable name in `engine/telegram/apps.py` and `apps/ops/apps.py` — admin edits are overwritten on save via `pre_save` signal.
- **Delivery retries**: scheduled `telegram_deliver` drains jobs that have not started delivery; it intentionally does not reset stale `delivery_started_at` jobs because an error after Telegram accepts a message would make an automatic resend duplicate the reply.
- **`policy.md`** is gitignored, loaded at runtime via `POLICY_FILE` env var.
- **Pre-commit**: runs `make lint` + `uv lock` on commit; `make test` + `make dead-code` + `make audit` on push.
- **Conventional commits** enforced via `conventional-pre-commit` hook on commit messages.
- **Semantic release**: `release` branch → stable, `main` → rc prereleases. Release commits auto-rebase open PRs.
- **Docker**: production uses `manage.py start` (qcluster + gunicorn); dev uses `manage.py dev` (qcluster + runserver).
